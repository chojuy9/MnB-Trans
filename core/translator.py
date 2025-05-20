import re
import time
import google.generativeai as genai
import google.api_core.exceptions as google_exceptions

# 메시지 타입 (main_window와 일치 또는 공유)
MSG_TYPE_PROGRESS = "progress"
MSG_TYPE_STATUS = "status"
MSG_TYPE_ERROR = "error"

DEFAULT_CHUNK_SIZE_FOR_TRANSLATOR = 50
# 실제 모델명은 GUI나 설정에서 받아오는 것이 이상적
# 여기서는 예시로 하드코딩. 실제 사용 가능한 모델명으로 변경 필요.
DEFAULT_MODEL_NAME = 'gemini-2.5-flash-preview-04-17'


class TextProcessor:
    def __init__(self, app_instance):
        self.app = app_instance

    def mnb_preprocess_text(self, text):
        replacements = {
            r"(\{s\d+\})": r"__MNBTAG_S\1__",
            r"(\{reg\d+\})": r"__MNBTAG_REG\1__",
            r"(\{player_name\})": r"__MNBTAG_PLAYERNAME__",
        }
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text)
        return text

    def mnb_postprocess_text(self, text):
        replacements_restore = {
            r"__MNBTAG_S(\{s\d+\})__": r"\1",
            r"__MNBTAG_REG(\{reg\d+\})__": r"\1",
            r"__MNBTAG_PLAYERNAME__": r"{player_name}",
        }
        for pattern, replacement in replacements_restore.items():
            text = re.sub(pattern, replacement, text)
        text = re.sub(r"{\s*([a-zA-Z_0-9]+)\s*}", r"{\1}", text)
        return text

    def _call_single_chunk_api(self, chunk_text, api_key, model_name, cancel_event, prompt_template_to_use):
        if cancel_event and cancel_event.is_set():
            return "CANCELLED"

        # genai.configure는 API 키가 변경될 때만 호출하거나, 전역적으로 한 번만 설정하는 것이 효율적일 수 있음
        # 스레드 환경에서는 API 클라이언트 객체를 매번 생성하거나 스레드 로컬 저장소를 사용하는 것이 더 안전할 수 있음
        # 현재는 단순성을 위해 매번 configure 호출 (Gemini 라이브러리의 스레드 안전성 확인 필요)
        try:
            genai.configure(api_key=api_key)
        except Exception as e_conf:
            self.app.put_message_in_queue(MSG_TYPE_ERROR, f"API 설정 오류: {e_conf}")
            raise ConnectionError(f"API 설정 실패: {e_conf}") from e_conf # 더 구체적인 예외로 변환 가능

        model = genai.GenerativeModel(model_name)

        if "{text_to_translate}" not in prompt_template_to_use:
            self.app.put_message_in_queue(MSG_TYPE_ERROR, "프롬프트 템플릿 형식이 잘못되었습니다. '{text_to_translate}' 플레이스홀더가 필요합니다.")
            # 이 경우, 작업을 중단시키기 위해 예외를 발생시킬 수 있음
            raise ValueError("잘못된 프롬프트 템플릿 형식")
        
        prompt_to_send = prompt_template_to_use.format(text_to_translate=chunk_text)

        try:
            # API 호출 타임아웃 설정 (선택 사항, 라이브러리 지원 여부 확인)
            # request_options = genai.types.RequestOptions(timeout=60) # 예시, 실제 API와 다를 수 있음
            # response = model.generate_content(prompt_to_send, request_options=request_options)
            response = model.generate_content(prompt_to_send)

            if cancel_event and cancel_event.is_set():
                return "CANCELLED"
            return response.text
        except Exception as e: # 여기서 잡히는 예외는 _call_single_chunk_api를 호출한 곳으로 전달됨
            if cancel_event and cancel_event.is_set():
                return "CANCELLED"
            # 여기서 바로 MSG_TYPE_ERROR를 큐에 넣기보다, 예외를 발생시켜 호출자가 처리하도록 함
            raise e


    def translate_by_chunks(self, full_text, api_key, chunk_size_lines=DEFAULT_CHUNK_SIZE_FOR_TRANSLATOR,
                          cancel_event=None, prompt_template=None, model_name_override=None):
        print(f"translate_by_chunks 실행 - chunk_size_lines: {chunk_size_lines}")
        if cancel_event and cancel_event.is_set():
            return "CANCELLED_BY_TRANSLATOR"

        if not api_key:
            self.app.put_message_in_queue(MSG_TYPE_ERROR, "API 키가 설정되지 않았습니다 (청크 번역).")
            return None # 또는 빈 문자열
        
        effective_model_name = model_name_override if model_name_override else DEFAULT_MODEL_NAME

        if not prompt_template:
            self.app.put_message_in_queue(MSG_TYPE_STATUS, "경고: 프롬프트 템플릿이 제공되지 않아 기본 형식 사용.")
            prompt_template = "Translate the following English text to Korean. Preserve any special placeholders (e.g., __MNBTAG_...__) exactly as they appear.\n\nEnglish Text:\n{text_to_translate}\n\nKorean Translation:"

        lines = full_text.splitlines(keepends=True)
        if not lines:
            self.app.put_message_in_queue(MSG_TYPE_PROGRESS, (0,1)) # (현재, 최대) -> 최대가 0이면 오류날 수 있으니 1로
            return ""

        translated_chunks = []
        total_lines = len(lines)
        total_chunks = (total_lines + chunk_size_lines - 1) // chunk_size_lines
        if total_chunks == 0 and total_lines > 0 : total_chunks = 1 # 최소 1개의 청크 (내용이 있을 경우)

        self.app.put_message_in_queue(MSG_TYPE_PROGRESS, (0, total_chunks if total_chunks > 0 else 1))

        for i in range(total_chunks):
            if cancel_event and cancel_event.is_set():
                self.app.put_message_in_queue(MSG_TYPE_STATUS, f"청크 {i+1}/{total_chunks} 처리 전 취소됨.")
                return "CANCELLED_BY_TRANSLATOR"

            chunk_start_line = i * chunk_size_lines
            chunk_end_line = min((i + 1) * chunk_size_lines, total_lines)
            current_chunk_lines = lines[chunk_start_line:chunk_end_line]
            current_chunk_text = "".join(current_chunk_lines)

            if not current_chunk_text.strip():
                translated_chunks.append(current_chunk_text)
                self.app.put_message_in_queue(MSG_TYPE_STATUS, f"청크 {i+1}/{total_chunks}: 내용 없음, 원본 유지.")
                self.app.put_message_in_queue(MSG_TYPE_PROGRESS, (i + 1, total_chunks))
                continue

            self.app.put_message_in_queue(MSG_TYPE_STATUS, f"청크 {i+1}/{total_chunks} 전처리 중...")
            preprocessed_chunk = self.mnb_preprocess_text(current_chunk_text)
            
            translated_chunk_raw = None
            api_error_message = None # 해당 청크의 API 오류 메시지 저장용
            try:
                self.app.put_message_in_queue(MSG_TYPE_STATUS, f"청크 {i+1}/{total_chunks} API 호출 ({effective_model_name})...")
                translated_chunk_raw = self._call_single_chunk_api(
                    preprocessed_chunk, api_key, effective_model_name, cancel_event, prompt_template
                )
                if translated_chunk_raw == "CANCELLED":
                    return "CANCELLED_BY_TRANSLATOR"

            except google_exceptions.PermissionDenied as e_perm:
                api_error_message = f"청크 {i+1}: API 권한 오류 - {e_perm}"
            except google_exceptions.ResourceExhausted as e_res:
                api_error_message = f"청크 {i+1}: API 리소스 오류 - {e_res}"
            except google_exceptions.DeadlineExceeded as e_dead:
                api_error_message = f"청크 {i+1}: API 시간 초과 - {e_dead}"
            except google_exceptions.GoogleAPIError as e_gapi: # 좀 더 일반적인 Google API 오류
                api_error_message = f"청크 {i+1}: Google API 오류 - {e_gapi}"
            except ValueError as e_val: # 프롬프트 템플릿 오류 등
                 api_error_message = f"청크 {i+1}: 입력값 오류 - {e_val}"
            except ConnectionError as e_conn: # API 설정 오류 등
                 api_error_message = f"청크 {i+1}: 연결 오류 - {e_conn}"
            except Exception as e_api: # 그 외 _call_single_chunk_api에서 발생한 모든 예외
                api_error_message = f"청크 {i+1}: API 호출 중 알 수 없는 오류 ({type(e_api).__name__}) - {e_api}"
            
            if api_error_message:
                self.app.put_message_in_queue(MSG_TYPE_ERROR, api_error_message) # 오류 메시지 큐에 전달
                translated_chunks.append(current_chunk_text) # 오류 시 원본 사용
                self.app.put_message_in_queue(MSG_TYPE_STATUS, f"청크 {i+1}/{total_chunks}: 오류로 원본 사용.")
                # 심각한 오류(예: API키 문제) 시 전체 번역 중단 결정 가능
                # if isinstance(e_perm, google_exceptions.PermissionDenied): return None
            elif translated_chunk_raw: # 성공적으로 번역됨
                self.app.put_message_in_queue(MSG_TYPE_STATUS, f"청크 {i+1}/{total_chunks} 후처리 중...")
                final_translated_chunk = self.mnb_postprocess_text(translated_chunk_raw.strip())
                translated_chunks.append(final_translated_chunk)
                # self.app.put_message_in_queue(MSG_TYPE_STATUS, f"청크 {i+1}/{total_chunks} 번역 완료.") # 너무 잦은 메시지일 수 있음
            else: # translated_chunk_raw is None or empty (but not "CANCELLED" or error)
                translated_chunks.append(current_chunk_text)
                self.app.put_message_in_queue(MSG_TYPE_STATUS, f"청크 {i+1}/{total_chunks}: API 응답 없음, 원본 사용.")

            self.app.put_message_in_queue(MSG_TYPE_PROGRESS, (i + 1, total_chunks))
            
            if cancel_event and cancel_event.is_set():
                self.app.put_message_in_queue(MSG_TYPE_STATUS, "작업 취소됨 (청크 처리 중).")
                return "CANCELLED_BY_TRANSLATOR"
            
            time.sleep(0.05) # CPU 사용률 완화 및 취소 감지 시간 확보 (매우 짧게)

        if cancel_event and cancel_event.is_set():
            return "CANCELLED_BY_TRANSLATOR"
            
        return "".join(translated_chunks)