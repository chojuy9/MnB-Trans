import json
import os

# main.py나 config_manager에서 프로젝트 루트를 참조하는 방식을 활용
# 여기서는 간단히 상대 경로 사용 (main.py 위치 기준)
DEFAULT_PROMPTS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "default_prompts.json")
# PyInstaller 등으로 패키징 시 경로 문제 해결을 위한 함수 (main.py에 정의된 resource_path 등 활용)
# def get_resource_path(relative_path):
#     try:
#         base_path = sys._MEIPASS # PyInstaller 임시 폴더
#     except Exception:
#         base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")) # core의 부모 폴더 (프로젝트 루트)
#     return os.path.join(base_path, relative_path)
# DEFAULT_PROMPTS_FILE = get_resource_path(os.path.join("data", "default_prompts.json"))


class PromptManager:
    def __init__(self, prompts_file_path=DEFAULT_PROMPTS_FILE):
        self.prompts_file_path = prompts_file_path
        self.prompts = self._load_prompts()
        if not self.prompts: # 로드 실패 또는 빈 파일 시 기본 프롬프트 제공
            self.prompts = [
                {
                    "id": "fallback_generic", "name": "기본 번역 (태그 보호)", "description": "가장 기본적인 번역을 수행합니다.",
                    "template": "Translate the following English text to Korean. Preserve any special placeholders (e.g., __MNBTAG_...__) exactly.\n\nEnglish:\n{text_to_translate}\n\nKorean:"
                }
            ]


    def _load_prompts(self):
        try:
            # 파일 경로가 실행 환경에 따라 달라질 수 있으므로 주의
            # PyInstaller 사용 시에는 sys._MEIPASS 등을 고려한 경로 처리 필요
            # 여기서는 main.py와 같은 레벨에 data 폴더가 있다고 가정
            
            # PyInstaller 호환성을 위해 경로를 좀 더 안전하게 만듭니다.
            # 이 prompt_manager.py 파일의 위치를 기준으로 상대 경로를 구성합니다.
            script_dir = os.path.dirname(os.path.abspath(__file__)) # core 폴더
            project_root = os.path.dirname(script_dir) # mnb_translator_project 폴더
            actual_prompts_file = os.path.join(project_root, "data", "default_prompts.json")

            if not os.path.exists(actual_prompts_file):
                print(f"경고: 프롬프트 파일 '{actual_prompts_file}'을(를) 찾을 수 없습니다.")
                return []
                
            with open(actual_prompts_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"경고: 프롬프트 파일 '{self.prompts_file_path}'을(를) 찾을 수 없습니다.")
            return []
        except json.JSONDecodeError:
            print(f"경고: 프롬프트 파일 '{self.prompts_file_path}'의 형식이 잘못되었습니다.")
            return []
        except Exception as e:
            print(f"프롬프트 로드 중 오류 발생: {e}")
            return []

    def get_prompt_names(self):
        """GUI Combobox에 표시할 프롬프트 이름 목록 반환"""
        return [p['name'] for p in self.prompts]

    def get_prompt_template_by_name(self, name):
        """이름으로 프롬프트 템플릿 찾기"""
        for p in self.prompts:
            if p['name'] == name:
                return p['template']
        return None # 못 찾으면 None 또는 기본 프롬프트 반환

    def get_prompt_template_by_id(self, prompt_id):
        """ID로 프롬프트 템플릿 찾기 (설정 저장/로드 시 ID 사용 권장)"""
        for p in self.prompts:
            if p['id'] == prompt_id:
                return p['template']
        # ID로 못 찾으면 첫 번째 프롬프트를 기본값으로 반환하거나, 특정 기본 ID의 프롬프트 반환
        return self.prompts[0]['template'] if self.prompts else None


    def get_default_prompt_id(self):
        """기본으로 선택될 프롬프트의 ID 반환 (예: 첫 번째 프롬프트)"""
        return self.prompts[0]['id'] if self.prompts else None
    
    def get_prompt_name_by_id(self, prompt_id):
        for p in self.prompts:
            if p['id'] == prompt_id:
                return p['name']
        return self.prompts[0]['name'] if self.prompts else None