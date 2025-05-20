import re
import google.generativeai as genai
import google.api_core.exceptions as google_exceptions
from tkinter import messagebox # GUI 의존성 최소화를 위해 messagebox는 app에서 전달받는 것이 좋으나, 편의상 직접 사용

# 이 클래스는 직접적인 GUI 업데이트(update_status)를 하지 않도록 수정 고려.
# 대신 결과를 반환하고, GUI 모듈에서 상태를 업데이트하도록 함.
# 여기서는 편의상 기존 구조 유지.

class TextProcessor:
    def __init__(self, app_instance):
        self.app = app_instance # GUI 인스턴스를 받아 상태 업데이트 등에 사용

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

    def call_gemini_api(self, text_to_translate, api_key):
        if not api_key:
            messagebox.showerror("API 키 오류", "Gemini API 키가 설정되지 않았습니다.")
            self.app.update_status("오류: API 키 누락") # app 인스턴스 통해 상태 업데이트
            return None
        try:
            genai.configure(api_key=api_key)
            # 모델명은 설정에서 가져오거나, 상수로 정의하는 것이 좋음
            model_name = 'gemini-2.5-flash-preview-04-17' # 실제 사용 가능한 모델명으로 변경 필요
            model = genai.GenerativeModel(model_name)
            prompt = f"""Translate the following English text from a Mount & Blade game mod into Korean.
Preserve special placeholders like __MNBTAG_S{{s0}}__, __MNBTAG_REG{{reg0}}__, or __MNBTAG_PLAYERNAME__ exactly as they are.
Do not translate the content inside these placeholders.
If the original text contains line breaks, try to maintain a similar structure in Korean if it makes sense.

English Text:
{text_to_translate}

Korean Translation:
"""
            self.app.update_status(f"{model_name} API 호출 중...")
            response = model.generate_content(prompt)
            self.app.update_status("API 응답 받음.")
            return response.text
        except google_exceptions.PermissionDenied as e:
            messagebox.showerror("API 권한 오류", f"API 키가 유효하지 않거나 권한이 없습니다.\n세부 정보: {e}")
            self.app.update_status(f"오류: API 권한 문제")
            return None
        except google_exceptions.ResourceExhausted as e:
            messagebox.showerror("API 리소스 오류", f"API 할당량을 초과했거나 리소스가 부족합니다.\n세부 정보: {e}")
            self.app.update_status(f"오류: API 리소스 문제")
            return None
        except google_exceptions.DeadlineExceeded as e:
            messagebox.showerror("API 시간 초과", f"API 호출 시간이 초과되었습니다.\n세부 정보: {e}")
            self.app.update_status(f"오류: API 시간 초과")
            return None
        except google_exceptions.GoogleAPIError as e:
            messagebox.showerror("Google API 오류", f"Google API 관련 오류 발생:\n세부 정보: {e}")
            self.app.update_status(f"오류: Google API 문제")
            return None
        except Exception as e:
            messagebox.showerror("API 알 수 없는 오류", f"Gemini API 호출 중 알 수 없는 오류 발생:\n세부 정보: {e}")
            self.app.update_status(f"오류: API 알 수 없는 오류")
            return None
