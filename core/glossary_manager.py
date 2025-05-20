import csv
import os
import re

# 메시지 타입 (main_window와 공유 또는 여기서 정의)
MSG_TYPE_STATUS = "status"
MSG_TYPE_ERROR = "error"

class GlossaryManager:
    def __init__(self, app_instance=None):
        self.app = app_instance # GUI 앱 인스턴스 (선택적, 상태 업데이트용)
        self.glossaries = {}  # {filepath: {original: translated}} 형태의 딕셔너리
        self.active_glossary_files = [] # 활성화된 용어집 파일 경로 목록

    def _send_status(self, message):
        if self.app and hasattr(self.app, 'put_message_in_queue'):
            self.app.put_message_in_queue(MSG_TYPE_STATUS, message)
        else:
            print(f"Status (GlossaryManager): {message}")

    def _send_error(self, message):
        if self.app and hasattr(self.app, 'put_message_in_queue'):
            self.app.put_message_in_queue(MSG_TYPE_ERROR, message)
        else:
            print(f"Error (GlossaryManager): {message}")


    def load_glossary_file(self, filepath):
        """지정된 CSV 용어집 파일을 로드하여 self.glossaries에 추가/갱신합니다."""
        if not os.path.exists(filepath):
            self._send_error(f"용어집 파일을 찾을 수 없습니다: {filepath}")
            return False
        
        term_map = {}
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f: # utf-8-sig for BOM
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    if len(row) == 2:
                        original, translated = row[0].strip(), row[1].strip()
                        if original: # 원본 용어가 비어있지 않아야 함
                            term_map[original] = translated
                    elif row: # 빈 행이 아니지만 형식이 잘못된 경우
                        self._send_status(f"경고: 용어집 파일 '{os.path.basename(filepath)}'의 {i+1}번째 줄 형식이 잘못되었습니다 (원본,번역 필요). 무시합니다.")
            
            self.glossaries[filepath] = term_map
            self._send_status(f"용어집 로드 완료: {os.path.basename(filepath)} ({len(term_map)}개 용어)")
            return True
        except Exception as e:
            self._send_error(f"용어집 파일 로드 중 오류 발생 ({os.path.basename(filepath)}): {e}")
            if filepath in self.glossaries: # 로드 중 오류 시 해당 용어집 제거
                del self.glossaries[filepath]
            return False

    def remove_glossary_file(self, filepath):
        """로드된 용어집에서 특정 파일을 제거합니다."""
        if filepath in self.glossaries:
            del self.glossaries[filepath]
            if filepath in self.active_glossary_files:
                self.active_glossary_files.remove(filepath)
            self._send_status(f"용어집 제거됨: {os.path.basename(filepath)}")
            return True
        return False

    def set_active_glossary_files(self, filepaths):
        """활성화할 용어집 파일 목록을 설정합니다. 목록에 없는 파일은 로드 시도합니다."""
        self.active_glossary_files = []
        newly_loaded_files = []
        for fp in filepaths:
            if fp not in self.glossaries: # 아직 로드되지 않은 파일이면 로드
                if self.load_glossary_file(fp):
                    self.active_glossary_files.append(fp)
                    newly_loaded_files.append(os.path.basename(fp))
                # else: 로드 실패 메시지는 load_glossary_file에서 처리
            elif fp not in self.active_glossary_files: # 이미 로드되었지만 활성 목록에 없다면 추가
                 self.active_glossary_files.append(fp)

        if newly_loaded_files:
            self._send_status(f"새 용어집 파일 로드 및 활성화: {', '.join(newly_loaded_files)}")
        # self._send_status(f"활성 용어집 업데이트됨: {len(self.active_glossary_files)}개 파일")


    def apply_glossary_to_text(self, text, use_exact_match=True, case_sensitive=False):
        """
        활성화된 모든 용어집을 텍스트에 적용합니다 (후처리 방식).
        가장 긴 용어부터 매칭하여 오적용을 줄이도록 시도합니다.
        use_exact_match: True이면 단어 단위 매칭 (\b), False이면 부분 문자열 매칭.
        case_sensitive: True이면 대소문자 구분.
        """
        if not self.active_glossary_files or not self.glossaries:
            return text

        combined_terms = {}
        for filepath in self.active_glossary_files:
            if filepath in self.glossaries:
                # 동일 원본 용어에 대해 나중에 로드/활성화된 용어집이 우선순위를 가짐 (덮어쓰기)
                combined_terms.update(self.glossaries[filepath]) 
        
        if not combined_terms:
            return text

        # 가장 긴 용어부터 처리하기 위해 길이순으로 정렬 (내림차순)
        # 동일 길이 내에서는 순서가 중요하지 않거나, 원래 순서 유지 가능
        sorted_originals = sorted(combined_terms.keys(), key=len, reverse=True)

        processed_text = text
        for original_term in sorted_originals:
            translated_term = combined_terms[original_term]
            
            # 정규식 패턴 생성
            # M&B 태그 내부의 내용은 치환 대상이 아님.
            # 예: {player_name}은 용어지만, 다른 태그 {s0} 내부의 player_name은 치환 안 함.
            # 이는 매우 복잡해질 수 있으므로, 초기에는 단순 치환.
            # 태그 보호는 mnb_preprocess_text/mnb_postprocess_text에서 이미 처리되었다고 가정.

            pattern_str = re.escape(original_term) # 정규식 특수문자 이스케이프
            if use_exact_match:
                pattern_str = r'\b' + pattern_str + r'\b' # 단어 경계

            try:
                if case_sensitive:
                    regex = re.compile(pattern_str)
                else:
                    regex = re.compile(pattern_str, re.IGNORECASE)
                
                processed_text = regex.sub(translated_term, processed_text)
            except re.error as e:
                self._send_error(f"용어집 정규식 오류 ('{original_term}'): {e}")
                continue # 다음 용어로 넘어감
        
        return processed_text

    def get_loaded_glossary_paths(self):
        return list(self.glossaries.keys())