import os
from tkinter import filedialog, messagebox # GUI 의존성. app에서 처리하도록 수정 고려

class FileHandler:
    def __init__(self, app_instance):
        self.app = app_instance # GUI 인스턴스를 받아 상태 업데이트 등에 사용

    def load_file(self):
        # 파일 열기 전, 현재 번역된 내용 저장 여부 확인 (GUI에서 처리하는 것이 더 적합)
        if self.app.unsaved_translation:
            if not messagebox.askokcancel("확인", "저장되지 않은 번역 내용이 있습니다. 계속 진행하시겠습니까?"):
                return None, None, False # filepath, content, is_csv_mode

        self.app.update_status("파일 여는 중...")
        filepath = filedialog.askopenfilename(
            defaultextension=".txt",
            filetypes=[("CSV files", "*.csv"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not filepath:
            self.app.update_status("파일 열기 취소됨.")
            return None, None, False

        file_extension = os.path.splitext(filepath)[1].lower()
        encodings_to_try = ['utf-8', 'cp1252', 'latin-1', 'euc-kr', 'cp949']
        content_to_display = ""
        is_csv_mode = False

        try:
            loaded_encoding = None
            with open(filepath, "rb") as f_bytes:
                raw_content_bytes = f_bytes.read()

            for enc in encodings_to_try:
                try:
                    content_to_display = raw_content_bytes.decode(enc)
                    loaded_encoding = enc
                    break
                except UnicodeDecodeError:
                    continue

            if loaded_encoding is None:
                messagebox.showerror("파일 읽기 오류", f"파일 인코딩을 확인할 수 없습니다 (시도: {', '.join(encodings_to_try)}): {filepath}")
                self.app.update_status("오류: 파일 인코딩 문제")
                return None, None, False

            if file_extension == ".csv":
                is_csv_mode = True
                self.app.update_status(f"CSV 파일 로드: {os.path.basename(filepath)} (인코딩: {loaded_encoding}). 전체 내용 표시.")
            else:
                self.app.update_status(f"TXT 파일 로드 완료: {os.path.basename(filepath)} (인코딩: {loaded_encoding})")

            self.app.unsaved_translation = False # 새 파일 로드 시 이전 번역은 의미 없음
            return filepath, content_to_display, is_csv_mode

        except FileNotFoundError:
            messagebox.showerror("파일 오류", f"파일을 찾을 수 없습니다: {filepath}")
            self.app.update_status(f"오류: 파일을 찾을 수 없음")
            return None, None, False
        except Exception as e:
            messagebox.showerror("파일 처리 오류", f"파일 처리 중 알 수 없는 오류 발생: {e}")
            self.app.update_status(f"오류: 파일 처리 실패 - {e}")
            return None, None, False

    def save_file(self, content_to_save, initial_filename_suggestion):
        if not content_to_save:
            messagebox.showwarning("저장 오류", "저장할 번역된 내용이 없습니다.")
            return False # 저장 실패

        self.app.update_status("번역 파일 저장 중...")
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=initial_filename_suggestion,
            filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not filepath:
            self.app.update_status("파일 저장 취소됨.")
            return False

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content_to_save)
            self.app.unsaved_translation = False # 저장했으므로
            messagebox.showinfo("저장 완료", "번역된 파일이 성공적으로 저장되었습니다.")
            self.app.update_status(f"파일 저장 완료: {os.path.basename(filepath)}")
            return True # 저장 성공
        except Exception as e:
            messagebox.showerror("파일 저장 오류", f"파일 저장 중 오류 발생: {e}")
            self.app.update_status(f"오류: 파일 저장 실패 - {e}")
            return False
