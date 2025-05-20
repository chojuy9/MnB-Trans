# core/translator.py

import re
import time # API 호출 간 딜레이를 위해 임포트 (선택 사항)
import google.generativeai as genai
import google.api_core.exceptions as google_exceptions
from tkinter import messagebox

# 청크 크기 (예: 줄 수) - 설정으로 빼거나 상수로 관리 가능
DEFAULT_CHUNK_SIZE_LINES = 50

class TextProcessor:
    def __init__(self, app_instance):
        self.app = app_instance

    def mnb_preprocess_text(self, text):
        # (기존 코드 동일)
        replacements = {
            r"(\{s\d+\})": r"__MNBTAG_S\1__",
            r"(\{reg\d+\})": r"__MNBTAG_REG\1__",
            r"(\{player_name\})": r"__MNBTAG_PLAYERNAME__",
        }
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text)
        return text

    def mnb_postprocess_text(self, text):
        # (기존 코드 동일)
        replacements_restore = {
            r"__MNBTAG_S(\{s\d+\})__": r"\1",
            r"__MNBTAG_REG(\{reg\d+\})__": r"\1",
            r"__MNBTAG_PLAYERNAME__": r"{player_name}",
        }
        for pattern, replacement in replacements_restore.items():
            text = re.sub(pattern, replacement, text)
        text = re.sub(r"{\s*([a-zA-Z_0-9]+)\s*}", r"{\1}", text)
        return text

    def _call_single_chunk_api(self, chunk_text, api_key, model_name):
        """단일 청크에 대해 API를 호출하는 내부 메소드"""
        # 이 메소드는 기존 call_gemini_api의 핵심 로직과 유사
        try:
            # genai.configure는 한 번만 호출해도 되지만, 안전을 위해 매번 호출하거나
            # TextProcessor 초기화 시 또는 API 키 변경 시 호출하도록 할 수 있음
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            prompt = f"""Translate the following English text from a Mount & Blade game mod into Korean.
Preserve special placeholders like __MNBTAG_S{{s0}}__, __MNBTAG_REG{{reg0}}__, or __MNBTAG_PLAYERNAME__ exactly as they are.
Do not translate the content inside these placeholders.
If the original text contains line breaks, try to maintain a similar structure in Korean if it makes sense.

English Text:
{chunk_text}

Korean Translation:
"""
            # self.app.update_status(...) # API 호출 상태는 translate_by_chunks에서 관리
            response = model.generate_content(prompt)
            return response.text
        except google_exceptions.PermissionDenied as e:
            # 오류 발생 시 None을 반환하고, 호출한 쪽에서 처리하도록 함
            # messagebox는 GUI 종속적이므로 여기서 직접 호출 X (또는 예외를 발생시켜 처리)
            print(f"API 권한 오류 (청크): {e}") # 콘솔 로깅 또는 app을 통한 로깅
            self.app.update_status(f"오류: API 권한 문제 (청크)")
            return None
        except google_exceptions.ResourceExhausted as e:
            print(f"API 리소스 오류 (청크): {e}")
            self.app.update_status(f"오류: API 리소스 문제 (청크)")
            return None
        # ... (다른 구체적인 예외 처리도 유사하게) ...
        except Exception as e:
            print(f"API 알 수 없는 오류 (청크): {e}")
            self.app.update_status(f"오류: API 알 수 없는 오류 (청크)")
            return None


    def translate_by_chunks(self, full_text, api_key, chunk_size_lines=DEFAULT_CHUNK_SIZE_FOR_TRANSLATOR):
        """텍스트를 청크 단위로 나누어 번역합니다."""
        if not api_key:
            # messagebox.showerror("API 키 오류", "Gemini API 키가 설정되지 않았습니다.") # GUI에서 처리
            self.app.update_status("오류: API 키 누락 (청크 번역)")
            return None # 또는 빈 문자열, 또는 예외 발생

        lines = full_text.splitlines(keepends=True) # 줄바꿈 문자 유지하며 분리
        translated_chunks = []
        total_chunks = (len(lines) + chunk_size_lines - 1) // chunk_size_lines # 올림 계산
        # chunk_size_lines = 50 # 기본값 또는 설정에서 가져오기

        model_name = 'gemini-2.5-flash-preview-04-17' # 설정 또는 상수로 관리

        for i in range(total_chunks):
            chunk_start_line = i * chunk_size_lines
            chunk_end_line = min((i + 1) * chunk_size_lines, len(lines))
            current_chunk_lines = lines[chunk_start_line:chunk_end_line]
            
            # 빈 줄만 있는 청크는 건너뛸 수 있지만, M&B 파일은 빈 줄도 의미가 있을 수 있으므로 일단 포함
            # if not any(line.strip() for line in current_chunk_lines):
            #     translated_chunks.append("".join(current_chunk_lines)) # 원본 그대로 추가
            #     self.app.update_status(f"청크 {i+1}/{total_chunks} 건너뜀 (빈 내용)")
            #     continue

            current_chunk_text = "".join(current_chunk_lines)
            if not current_chunk_text.strip(): # 실제로 내용이 없는 청크
                 translated_chunks.append(current_chunk_text)
                 self.app.update_status(f"청크 {i+1}/{total_chunks} 번역 중... (빈 청크, 원본 유지)")
                 continue


            self.app.update_status(f"청크 {i+1}/{total_chunks} 번역 준비 중...")

            # 1. 각 청크 전처리
            preprocessed_chunk = self.mnb_preprocess_text(current_chunk_text)
            
            self.app.update_status(f"청크 {i+1}/{total_chunks} API 호출 ({model_name})...")
            # 2. API 호출
            translated_chunk_raw = self._call_single_chunk_api(preprocessed_chunk, api_key, model_name)

            if translated_chunk_raw:
                # 3. 각 청크 후처리
                final_translated_chunk = self.mnb_postprocess_text(translated_chunk_raw.strip())
                translated_chunks.append(final_translated_chunk)
                self.app.update_status(f"청크 {i+1}/{total_chunks} 번역 완료.")
            else:
                # API 호출 실패 시 처리
                self.app.update_status(f"청크 {i+1}/{total_chunks} 번역 실패. 원본을 사용합니다.")
                # 실패한 청크는 원본 텍스트(전처리 전)를 사용하거나, 사용자에게 알림
                # 여기서는 원본 청크 텍스트를 그대로 추가 (후처리 없이)
                # 또는 전처리된 텍스트를 복원(__MNBTAG__ 제거)해서 넣을 수도 있음
                translated_chunks.append(current_chunk_text) # 원본 청크 사용
                # (선택) 오류 발생 시 전체 번역 중단 여부 결정
                # if messagebox.askretrycancel("청크 번역 오류", f"청크 {i+1} 번역에 실패했습니다. 계속하시겠습니까?"):
                #     continue # 다음 청크로
                # else:
                #     return None # 전체 번역 중단

            # (선택) API 호출 간 딜레이
            # time.sleep(0.5) # 예: 0.5초 대기

        return "\n".join(translated_chunks) # 최종 번역 결과 병합 (줄바꿈 복원 주의)
                                            # splitlines(keepends=True)로 했으므로 join시 \n 불필요할 수 있음
                                            # -> "".join(translated_chunks) 로 수정 필요할 수 있음
                                            # 후처리된 청크가 줄바꿈을 포함하고 있는지 확인 필요.
                                            # 보통 API 응답은 줄바꿈을 포함하므로 ""join이 적절.
