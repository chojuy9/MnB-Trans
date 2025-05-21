# core/config_manager.py
import os
import json
import sys

# --- 경로 설정 ---
try:
    if hasattr(sys, '_MEIPASS'):
        PROJECT_ROOT = sys._MEIPASS
        USER_DATA_DIR = os.path.join(PROJECT_ROOT, "user_data")
    else:
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        USER_DATA_DIR = os.path.join(PROJECT_ROOT, "user_data")
except NameError: # sys가 없는 매우 예외적인 환경 (예: 특정 임베디드 Python)
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    USER_DATA_DIR = os.path.join(PROJECT_ROOT, "user_data")

CONFIG_FILE_NAME = "config.json"
CONFIG_FILE_PATH = os.path.join(USER_DATA_DIR, CONFIG_FILE_NAME)

# --- 설정 키 이름 상수 ---
API_KEY_NAME_IN_CONFIG = "gemini_api_key"
CHUNK_SIZE_NAME_IN_CONFIG = "chunk_size_lines"
SELECTED_PROMPT_ID_NAME_IN_CONFIG = "selected_prompt_id"
ACTIVE_GLOSSARY_FILES_NAME_IN_CONFIG = "active_glossary_files"
SELECTED_MODEL_ID_NAME_IN_CONFIG = "selected_model_id"

# --- 기본값 ---
DEFAULT_CHUNK_SIZE = 50

# --- 사용 가능한 모델 및 모델별 스레드 설정 ---
# (모델 ID: 사용자 표시 이름)
AVAILABLE_MODELS = {
    # "gemini-1.5-flash-latest": "Gemini 1.5 Flash (빠름, 균형, 최신)", 구버전에 성능 나쁨
    # "gemini-1.5-pro-latest": "Gemini 1.5 Pro (고품질, 균형, 최신)", 구버전에 지능 떨어짐
    # "gemini-pro": "Gemini 1.0 Pro (일반 Pro)", 구 버전 Pro
    # "gemini-1.0-pro-001": "Gemini 1.0 Pro 001", 특정 버전 명시가 필요할 경우
    "gemini-2.0-flash-preview-image-generation": "Gemini 2.0 Flash (저품질, 무료)", # 기본으로 폴백 (무료임)
    "gemini-2.5-flash-preview-05-20": "Gemini 2.5 flash preview 05-20 (고품질, 유료, 저렴함)", # 빠르고 능지도 나쁘지 않지만 유료임
    "gemini-2.0-flash-lite": "Gemini 2.0 Flash Lite (빠름, 저급, 유료, 매우 저렴함)", # 빠르지만 능지 떨어짐
    "gemini-2.5-pro-preview-05-06": "Gemini 2.5 Pro preview 05-06 (고품질, 유료, 비쌈)", # 느리고 비싸지만 퀄리티는 확실함
    # 참고: Gemini API 문서에서 정확한 최신 모델 ID를 확인하세요.
    # 예시로 최신 안정화 모델 위주로 남깁니다. 프리뷰 모델은 자주 변경될 수 있습니다.
}
# AVAILABLE_MODELS의 첫 번째 키를 기본값으로 사용
DEFAULT_MODEL_ID = next(iter(AVAILABLE_MODELS)) if AVAILABLE_MODELS else "gemini-2.0-flash-preview-image-generation"


# 모델별 권장 스레드 수 (키는 AVAILABLE_MODELS의 키와 일치)
# 실제 RPM과 테스트를 통해 최적의 값으로 조정해야 합니다.
MODEL_THREAD_CONFIG = {
    # "gemini-1.5-flash-latest": 6,
    # "gemini-1.5-pro-latest": 3,
    # "gemini-pro": 3,
    # "gemini-1.0-pro-001": 3,
    "gemini-2.0-flash-lite": 6,
    "gemini-2.5-flash-preview-05-20": 3,
    "gemini-2.5-pro-preview-05-06": 2,
    "gemini-2.0-flash-preview-image-generation": 4,
    "default": 3  # MODEL_THREAD_CONFIG에 명시되지 않은 모델의 기본 스레드 수
}

def load_config():
    # 기본 설정값 구조
    config = {
        API_KEY_NAME_IN_CONFIG: "",
        CHUNK_SIZE_NAME_IN_CONFIG: DEFAULT_CHUNK_SIZE,
        SELECTED_PROMPT_ID_NAME_IN_CONFIG: None, # GUI에서 기본 프롬프트 ID로 초기화
        ACTIVE_GLOSSARY_FILES_NAME_IN_CONFIG: [],
        SELECTED_MODEL_ID_NAME_IN_CONFIG: DEFAULT_MODEL_ID
    }
    if not os.path.exists(USER_DATA_DIR):
        try:
            os.makedirs(USER_DATA_DIR)
        except OSError as e:
            print(f"경고: 사용자 데이터 폴더 생성 실패 ({USER_DATA_DIR}): {e}")
            # 폴더 생성 실패 시에도 기본 설정으로 계속 진행

    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, "r", encoding='utf-8') as f:
                loaded_config = json.load(f)
                # 로드된 설정으로 기본값 덮어쓰기 (없는 키는 기본값 유지)
                for key, default_value in config.items():
                    config[key] = loaded_config.get(key, default_value)
                
                # 로드된 모델 ID가 AVAILABLE_MODELS에 없으면 기본값으로 설정
                if config[SELECTED_MODEL_ID_NAME_IN_CONFIG] not in AVAILABLE_MODELS:
                    print(f"경고: 저장된 모델 ID '{config[SELECTED_MODEL_ID_NAME_IN_CONFIG]}'가 현재 사용 불가능합니다. 기본 모델로 재설정합니다.")
                    config[SELECTED_MODEL_ID_NAME_IN_CONFIG] = DEFAULT_MODEL_ID

        except Exception as e:
            print(f"설정 파일 로드 오류 ({CONFIG_FILE_PATH}): {e}. 기본 설정을 사용합니다.")
            # 오류 발생 시 config는 초기 기본값 상태 유지
    return config

def save_config(config_data):
    try:
        if not os.path.exists(USER_DATA_DIR):
            os.makedirs(USER_DATA_DIR) # 저장 시에도 폴더 확인 및 생성
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

# 편의 함수에 모델 관련 추가 (선택적)
def load_selected_model_id():
    return load_config().get(SELECTED_MODEL_ID_NAME_IN_CONFIG, DEFAULT_MODEL_ID)

def save_selected_model_id(model_id):
    conf = load_config()
    conf[SELECTED_MODEL_ID_NAME_IN_CONFIG] = model_id
    return save_config(conf)