import os
import json

# 프로젝트 루트를 기준으로 user_data 폴더 경로 설정
# main.py가 프로젝트 루트에 있다고 가정
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # core 폴더의 부모 폴더 (mnb_translator_project)
USER_DATA_DIR = os.path.join(PROJECT_ROOT, "user_data")
CONFIG_FILE_NAME = "config.json"
CONFIG_FILE_PATH = os.path.join(USER_DATA_DIR, CONFIG_FILE_NAME)

API_KEY_NAME_IN_CONFIG = "gemini_api_key"

def load_api_key():
    """설정 파일에서 API 키를 로드합니다."""
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, "r") as f:
                config = json.load(f)
                return config.get(API_KEY_NAME_IN_CONFIG, "")
        except Exception:
            # 오류 발생 시 빈 문자열 반환 (또는 로깅)
            return ""
    return ""

def save_api_key(api_key):
    """API 키를 설정 파일에 저장합니다."""
    try:
        # user_data 폴더가 없으면 생성 (main.py에서도 하지만, 여기서도 방어적으로)
        if not os.path.exists(USER_DATA_DIR):
            os.makedirs(USER_DATA_DIR)

        with open(CONFIG_FILE_PATH, "w") as f:
            json.dump({API_KEY_NAME_IN_CONFIG: api_key}, f)
        return True
    except Exception:
        return False

# 향후 다른 설정 관리 함수들도 여기에 추가 가능
