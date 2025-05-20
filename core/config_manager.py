# core/config_manager.py
import os
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USER_DATA_DIR = os.path.join(PROJECT_ROOT, "user_data")
CONFIG_FILE_NAME = "config.json"
CONFIG_FILE_PATH = os.path.join(USER_DATA_DIR, CONFIG_FILE_NAME)

API_KEY_NAME_IN_CONFIG = "gemini_api_key"
CHUNK_SIZE_NAME_IN_CONFIG = "chunk_size_lines"
DEFAULT_CHUNK_SIZE = 50 # 기본 청크 크기

def load_config():
    """설정 파일에서 전체 설정을 로드합니다."""
    config = {
        API_KEY_NAME_IN_CONFIG: "",
        CHUNK_SIZE_NAME_IN_CONFIG: DEFAULT_CHUNK_SIZE
    }
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, "r") as f:
                loaded_config = json.load(f)
                config.update(loaded_config) # 로드된 값으로 기본값 덮어쓰기
        except Exception as e:
            print(f"설정 파일 로드 오류: {e}") # 또는 로깅
    return config

def save_config(config_data):
    """전체 설정을 설정 파일에 저장합니다."""
    try:
        if not os.path.exists(USER_DATA_DIR):
            os.makedirs(USER_DATA_DIR)
        with open(CONFIG_FILE_PATH, "w") as f:
            json.dump(config_data, f, indent=4) # 보기 좋게 indent 추가
        return True
    except Exception as e:
        print(f"설정 파일 저장 오류: {e}")
        return False

# 기존 API 키 관련 함수는 유지하거나, 위 load_config/save_config를 사용하도록 수정
def load_api_key_specific(): # 이름 변경하여 구분
    config = load_config()
    return config.get(API_KEY_NAME_IN_CONFIG, "")

def save_api_key_specific(api_key): # 이름 변경하여 구분
    current_config = load_config()
    current_config[API_KEY_NAME_IN_CONFIG] = api_key
    return save_config(current_config)

def load_chunk_size():
    config = load_config()
    return config.get(CHUNK_SIZE_NAME_IN_CONFIG, DEFAULT_CHUNK_SIZE)

def save_chunk_size(chunk_size):
    current_config = load_config()
    current_config[CHUNK_SIZE_NAME_IN_CONFIG] = chunk_size
    return save_config(current_config)