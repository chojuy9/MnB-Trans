import tkinter as tk
import os # user_data 폴더 생성 위해 임포트
from gui.main_window import CoreTranslatorApp
from core.config_manager import USER_DATA_DIR # 사용자 데이터 폴더 경로 가져오기

def main():
    # 사용자 데이터 폴더가 없으면 생성
    if not os.path.exists(USER_DATA_DIR):
        try:
            os.makedirs(USER_DATA_DIR)
            print(f"사용자 데이터 폴더 생성: {USER_DATA_DIR}")
        except OSError as e:
            print(f"사용자 데이터 폴더 생성 실패: {e}")
            # 폴더 생성 실패 시 프로그램 종료 또는 다른 처리
            return

    root = tk.Tk()
    app = CoreTranslatorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
