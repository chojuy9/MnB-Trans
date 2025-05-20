import os
import json

# 프로젝트 루트를 기준으로 user_data 폴더 경로 설정
# 이 파일(config_manager.py)은 core 폴더 내에 있으므로, 부모의 부모 폴더가 프로젝트 루트.
try:
    # PyInstaller로 빌드된 경우 sys._MEIPASS를 사용해야 할 수 있음
    # 일반 실행 시에는 __file__을 기준으로 경로 설정
    if hasattr(sys, '_MEIPASS'):
        PROJECT_ROOT = sys._MEIPASS
        USER_DATA_DIR = os.path.join(PROJECT_ROOT, "user_data") # 실행 파일 위치 기준 user_data
    else:
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        USER_DATA_DIR = os.path.join(PROJECT_ROOT, "user_data")
except NameError: # sys 모듈이 아직 임포트되지 않은 경우 (예: 테스트 환경)
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    USER_DATA_DIR = os.path.join(PROJECT_ROOT, "user_data")


CONFIG_FILE_NAME = "config.json"
CONFIG_FILE_PATH = os.path.join(USER_DATA_DIR, CONFIG_FILE_NAME)

# 설정 키 이름 상수화
API_KEY_NAME_IN_CONFIG = "gemini_api_key"
CHUNK_SIZE_NAME_IN_CONFIG = "chunk_size_lines"
SELECTED_PROMPT_ID_NAME_IN_CONFIG = "selected_prompt_id"
ACTIVE_GLOSSARY_FILES_NAME_IN_CONFIG = "active_glossary_files"

DEFAULT_CHUNK_SIZE = 50 # 기본 청크 크기 (다른 곳에서도 참조 가능하도록) 

def load_config():
    """설정 파일에서 전체 설정을 로드합니다."""
    config = {
        API_KEY_NAME_IN_CONFIG: "",
        CHUNK_SIZE_NAME_IN_CONFIG: DEFAULT_CHUNK_SIZE,
        SELECTED_PROMPT_ID_NAME_IN_CONFIG: None,
        ACTIVE_GLOSSARY_FILES_NAME_IN_CONFIG: [] # 기본값은 빈 리스트
    }
    if not os.path.exists(USER_DATA_DIR): # user_data 폴더가 없으면 생성 시도
        try:
            os.makedirs(USER_DATA_DIR)
        except OSError as e:
            print(f"경고: 사용자 데이터 폴더 생성 실패 ({USER_DATA_DIR}): {e}")
            # 폴더 생성 실패 시 기본 설정만 반환

    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, "r", encoding='utf-8') as f:
                loaded_config = json.load(f)
                # ACTIVE_GLOSSARY_FILES_NAME_IN_CONFIG 키가 없을 경우 대비
                if ACTIVE_GLOSSARY_FILES_NAME_IN_CONFIG not in loaded_config:
                    loaded_config[ACTIVE_GLOSSARY_FILES_NAME_IN_CONFIG] = []
                config.update(loaded_config)
        except Exception as e:
            print(f"설정 파일 로드 오류 ({CONFIG_FILE_PATH}): {e}")
    return config

# 편의 함수
def load_active_glossary_files():
    return load_config().get(ACTIVE_GLOSSARY_FILES_NAME_IN_CONFIG, [])

def save_active_glossary_files(filepaths):
    conf = load_config()
    conf[ACTIVE_GLOSSARY_FILES_NAME_IN_CONFIG] = filepaths
    return save_config(conf)

def save_config(config_data):
    """전체 설정을 설정 파일에 저장합니다."""
    try:
        if not os.path.exists(USER_DATA_DIR):
            os.makedirs(USER_DATA_DIR)
        with open(CONFIG_FILE_PATH, "w", encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"설정 파일 저장 오류 ({CONFIG_FILE_PATH}): {e}")
        return False

# 편의 함수들 (선택적)
def load_api_key():
    return load_config().get(API_KEY_NAME_IN_CONFIG, "")

def save_api_key(api_key):
    conf = load_config()
    conf[API_KEY_NAME_IN_CONFIG] = api_key
    return save_config(conf)

def load_chunk_size():
    return load_config().get(CHUNK_SIZE_NAME_IN_CONFIG, DEFAULT_CHUNK_SIZE)

def save_chunk_size(chunk_size):
    conf = load_config()
    conf[CHUNK_SIZE_NAME_IN_CONFIG] = chunk_size
    return save_config(conf)

def load_selected_prompt_id():
    return load_config().get(SELECTED_PROMPT_ID_NAME_IN_CONFIG)

def save_selected_prompt_id(prompt_id):
    conf = load_config()
    conf[SELECTED_PROMPT_ID_NAME_IN_CONFIG] = prompt_id
    return save_config(conf)