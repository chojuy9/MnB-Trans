# core/translator.py
import re
import time
import google.generativeai as genai
import google.api_core.exceptions as google_exceptions
from concurrent.futures import ThreadPoolExecutor, as_completed, CancelledError

# config_manager에서 모델별 스레드 설정을 가져옴
from core.config_manager import MODEL_THREAD_CONFIG, DEFAULT_MODEL_ID

# 메시지 타입
MSG_TYPE_PROGRESS = "progress"
MSG_TYPE_STATUS = "status"
MSG_TYPE_ERROR = "error"

DEFAULT_CHUNK_SIZE_FOR_TRANSLATOR = 50
FALLBACK_DEFAULT_MODEL_NAME = DEFAULT_MODEL_ID # config_manager의 기본 모델 ID 사용

# API 호출 재시도 설정
MAX_RETRIES = 2  # 최대 재시도 횟수
INITIAL_RETRY_DELAY = 1  # 초기 재시도 대기 시간 (초)

class TextProcessor:
    def __init__(self, app_instance):
        self.app = app_instance # GUI 앱 인스턴스 참조

    def mnb_preprocess_text(self, text):
        # ... (기존과 동일)
        replacements = {
            r"(\{s\d+\})": r"__MNBTAG_S\1__",
            r"(\{reg\d+\})": r"__MNBTAG_REG\1__",
            r"(\{player_name\})": r"__MNBTAG_PLAYERNAME__",
        }
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text)
        return text

    def mnb_postprocess_text(self, text):
        # ... (기존과 동일)
        replacements_restore = {
            r"__MNBTAG_S(\{s\d+\})__": r"\1",
            r"__MNBTAG_REG(\{reg\d+\})__": r"\1",
            r"__MNBTAG_PLAYERNAME__": r"{player_name}",
        }
        for pattern, replacement in replacements_restore.items():
            text = re.sub(pattern, replacement, text)
        text = re.sub(r"{\s*([a-zA-Z_0-9]+)\s*}", r"{\1}", text)
        return text

    def _is_retryable_error(self, exception):
        """재시도 가능한 API 오류인지 확인"""
        if isinstance(exception, (google_exceptions.ServiceUnavailable,  # 503
                                   google_exceptions.TooManyRequests,   # 429 (RPM 초과)
                                   google_exceptions.DeadlineExceeded,  # 타임아웃
                                   google_exceptions.InternalServerError, # 500
                                   ConnectionError)): # 네트워크 연결 문제
            return True
        # 특정 오류 코드나 메시지 기반으로 더 세분화 가능
        # if hasattr(exception, 'code') and exception.code() == 특정코드: return True
        return False

    def _call_single_chunk_api_with_retry(self, chunk_text, api_key, model_name_to_use, prompt_template_to_use, current_chunk_index_for_debug="N/A"):
        """API 호출 및 재시도 로직 포함"""
        try:
            genai.configure(api_key=api_key)
        except Exception as e_conf:
            # API 키 설정 실패는 재시도 대상이 아님
            raise ConnectionError(f"청크 {current_chunk_index_for_debug}: API 키 설정 실패 - {e_conf}") from e_conf

        model = genai.GenerativeModel(model_name_to_use)

        if "{text_to_translate}" not in prompt_template_to_use:
            raise ValueError(f"청크 {current_chunk_index_for_debug}: 잘못된 프롬프트 템플릿 형식입니다. '{'{text_to_translate}'}' 플레이스홀더가 필요합니다.")
        
        prompt_to_send = prompt_template_to_use.format(text_to_translate=chunk_text)
        
        retries = 0
        last_exception = None
        while retries <= MAX_RETRIES:
            try:
                response = model.generate_content(prompt_to_send)
                return response.text
            except Exception as e:
                last_exception = e
                if self._is_retryable_error(e) and retries < MAX_RETRIES:
                    delay = INITIAL_RETRY_DELAY * (2 ** retries) # Exponential backoff
                    self.app.put_message_in_queue(
                        MSG_TYPE_STATUS,
                        f"청크 {current_chunk_index_for_debug}: API 오류 ({type(e).__name__}), {delay}초 후 재시도 ({retries + 1}/{MAX_RETRIES})..."
                    )
                    time.sleep(delay)
                    retries += 1
                else: # 재시도 불가 또는 최대 재시도 도달
                    raise e # 원래 예외를 다시 발생시켜 상위에서 처리
        
        # 이 지점에 도달하면 안 되지만, 만약을 위해 (모든 재시도 실패)
        if last_exception:
            raise last_exception
        return None # 이론상 도달 불가


    def translate_by_chunks(self, full_text, api_key, chunk_size_lines=DEFAULT_CHUNK_SIZE_FOR_TRANSLATOR,
                          cancel_event=None, prompt_template=None, model_name_override=None):
        if cancel_event and cancel_event.is_set():
            return "CANCELLED_BY_TRANSLATOR" # 작업 취소 시 특별한 문자열 반환
        if not api_key:
            self.app.put_message_in_queue(MSG_TYPE_ERROR, "API 키가 설정되지 않았습니다.")
            return None # API 키 없으면 진행 불가
        
        effective_model_name = model_name_override if model_name_override else FALLBACK_DEFAULT_MODEL_NAME
        
        # 모델별 스레드 수 결정 (config_manager에서 가져온 MODEL_THREAD_CONFIG 사용)
        num_workers_for_model = MODEL_THREAD_CONFIG.get(effective_model_name, MODEL_THREAD_CONFIG.get("default", 3))
        
        # 사용자에게 현재 작업 설정 알림
        self.app.put_message_in_queue(
            MSG_TYPE_STATUS,
            f"번역 작업 시작 (모델: {effective_model_name}, 청크: {chunk_size_lines}줄, 최대 스레드: {num_workers_for_model})"
        )

        if not prompt_template: # 프롬프트 템플릿이 없는 경우 기본값 사용 및 알림
            self.app.put_message_in_queue(MSG_TYPE_STATUS, "경고: 프롬프트 템플릿이 제공되지 않아 내부 기본 형식을 사용합니다.")
            prompt_template = "Translate the following English text to Korean. Preserve any special placeholders (e.g., __MNBTAG_...__) exactly as they appear.\n\nEnglish Text:\n{text_to_translate}\n\nKorean Translation:"

        lines = full_text.splitlines(keepends=True) # 줄바꿈 문자 유지를 위해 keepends=True
        if not lines: # 입력 텍스트가 비어있는 경우
            self.app.put_message_in_queue(MSG_TYPE_PROGRESS, (1, 1)) # 진행률 100%
            return "" # 빈 문자열 반환

        # 청크 분리
        chunks_to_process = []
        for i in range(0, len(lines), chunk_size_lines):
            if cancel_event and cancel_event.is_set(): break
            chunk_lines = lines[i : min(i + chunk_size_lines, len(lines))]
            chunk_text = "".join(chunk_lines)
            if chunk_text.strip(): # 내용이 있는 청크만 전처리
                preprocessed_chunk = self.mnb_preprocess_text(chunk_text)
                chunks_to_process.append({"index": len(chunks_to_process), "original_text": chunk_text, "processed_text": preprocessed_chunk, "is_empty": False})
            else: # 빈 줄로만 이루어진 청크
                chunks_to_process.append({"index": len(chunks_to_process), "original_text": chunk_text, "processed_text": None, "is_empty": True})

        # 실제 번역이 필요한 청크 수 계산
        total_translatable_chunks = sum(1 for c in chunks_to_process if not c.get("is_empty"))
        
        if total_translatable_chunks == 0: # 번역할 내용이 없는 경우 (모두 빈 줄)
            self.app.put_message_in_queue(MSG_TYPE_PROGRESS, (1, 1))
            return full_text # 원본 텍스트 그대로 반환

        # 초기 진행률 설정
        self.app.put_message_in_queue(MSG_TYPE_PROGRESS, (0, total_translatable_chunks))
        
        translated_results = [None] * len(chunks_to_process) # 각 청크의 번역 결과를 저장할 리스트
        processed_api_chunks_count = 0 # API 호출로 처리된 청크 수 (진행률용)

        with ThreadPoolExecutor(max_workers=num_workers_for_model) as executor:
            future_to_chunk_info = {}
            for chunk_info in chunks_to_process:
                if cancel_event and cancel_event.is_set(): break # 작업 취소 감지
                
                if chunk_info.get("is_empty"): # 빈 청크는 API 호출 없이 원본 사용
                    translated_results[chunk_info["index"]] = chunk_info["original_text"]
                    continue # 다음 청크로

                # API 호출 작업 제출
                future = executor.submit(self._call_single_chunk_api_with_retry, # 재시도 로직 포함된 함수로 변경
                                         chunk_info["processed_text"], api_key,
                                         effective_model_name,
                                         prompt_template,
                                         current_chunk_index_for_debug=chunk_info["index"] + 1)
                future_to_chunk_info[future] = chunk_info

            # 완료된 작업 순서대로 결과 처리
            for future in as_completed(future_to_chunk_info):
                if cancel_event and cancel_event.is_set(): # 작업 취소 감지
                    self.app.put_message_in_queue(MSG_TYPE_STATUS, "취소 요청으로 결과 처리를 중단합니다.")
                    # 이미 제출된 다른 future들을 취소 시도 (실행 중인 작업은 즉시 중단 안될 수 있음)
                    for f_other in future_to_chunk_info.keys():
                        if not f_other.done(): f_other.cancel()
                    return "CANCELLED_BY_TRANSLATOR"

                chunk_info_completed = future_to_chunk_info[future]
                original_idx = chunk_info_completed["index"]
                original_chunk_text_for_fallback = chunk_info_completed["original_text"]
                
                try:
                    translated_chunk_raw = future.result() # 예외 발생 가능성 있음
                    
                    if translated_chunk_raw: # 성공적인 번역 결과
                        final_translated_chunk = self.mnb_postprocess_text(translated_chunk_raw.strip())
                        translated_results[original_idx] = final_translated_chunk
                        # self.app.put_message_in_queue(MSG_TYPE_STATUS, f"청크 {original_idx+1} 번역 완료.") # 너무 잦은 메시지, 진행률로 대체
                    else: # API가 None이나 빈 문자열 반환 (비정상적)
                        translated_results[original_idx] = original_chunk_text_for_fallback
                        self.app.put_message_in_queue(MSG_TYPE_STATUS, f"경고: 청크 {original_idx+1}에서 API가 빈 응답을 반환하여 원본을 사용합니다.")
                
                except CancelledError: # future.cancel()이 명시적으로 성공한 경우
                     translated_results[original_idx] = original_chunk_text_for_fallback
                     self.app.put_message_in_queue(MSG_TYPE_STATUS, f"청크 {original_idx+1} 작업이 명시적으로 취소되었습니다.")
                except (google_exceptions.PermissionDenied, ConnectionError, ValueError) as e_specific:
                    # _call_single_chunk_api_with_retry에서 재시도 후에도 실패한 특정 오류들
                    translated_results[original_idx] = original_chunk_text_for_fallback
                    self.app.put_message_in_queue(MSG_TYPE_ERROR, f"청크 {original_idx+1} 처리 중 오류: {type(e_specific).__name__} - {str(e_specific)[:100]}. 원본을 사용합니다.")
                    if isinstance(e_specific, google_exceptions.PermissionDenied) or \
                       (isinstance(e_specific, ConnectionError) and "API 키 설정 실패" in str(e_specific)):
                        # API 키 문제나 권한 문제는 심각, 전체 번역 중단
                        self.app.put_message_in_queue(MSG_TYPE_STATUS, "API 키 또는 권한 문제로 번역을 중단합니다.")
                        for f_other in future_to_chunk_info.keys(): # 나머지 작업 취소
                            if not f_other.done(): f_other.cancel()
                        return None # None 반환으로 GUI에서 전체 오류 처리
                except Exception as e_general: # 그 외 모든 예외 (API 호출 중 발생)
                    translated_results[original_idx] = original_chunk_text_for_fallback
                    self.app.put_message_in_queue(MSG_TYPE_ERROR, f"청크 {original_idx+1} 처리 중 예기치 않은 오류: {type(e_general).__name__} - {str(e_general)[:100]}. 원본을 사용합니다.")
                
                processed_api_chunks_count += 1
                self.app.put_message_in_queue(MSG_TYPE_PROGRESS, (processed_api_chunks_count, total_translatable_chunks))

        if cancel_event and cancel_event.is_set():
            return "CANCELLED_BY_TRANSLATOR"
        
        # 모든 청크 결과 조합 전, 누락된 결과가 있는지 최종 확인
        for idx in range(len(chunks_to_process)):
            if translated_results[idx] is None: # 어떤 이유로든 결과가 None이면 원본으로 대체
                translated_results[idx] = chunks_to_process[idx]["original_text"]
                self.app.put_message_in_queue(MSG_TYPE_STATUS, f"경고: 청크 {idx+1}의 최종 결과가 누락되어 원본으로 대체합니다.")
        
        return "".join(translated_results) # 모든 청크의 (번역 또는 원본) 텍스트를 합쳐 반환