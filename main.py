import os
import re
import fitz  # PyMuPDF (화면 출력 오류 방지용 내장 렌더링 엔진)
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from rapidocr_onnxruntime import RapidOCR

class PDFRenamerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("오프라인 PDF 특정위치 숫자 인식 & 파일명 변경기")
        self.root.geometry("950x800")

        # 오프라인 OCR 엔진 초기화 (내장 모델 사용)
        self.ocr = RapidOCR()

        self.folder_path = ""
        self.pdf_files = []
        self.sample_image = None
        self.tk_image = None
        self.scale_factor = 1.0
        
        # 마우스 드래그 좌표 저장용
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.crop_box = None  # 원본 이미지 기준 (x1, y1, x2, y2)

        self.setup_ui()

    def setup_ui(self):
        # 상단 버튼 프레임
        top_frame = tk.Frame(self.root, pady=10, padx=10, bg="#f0f0f0")
        top_frame.pack(fill=tk.X)

        btn_folder = tk.Button(top_frame, text="1. PDF 폴더 선택", command=self.select_folder, font=("맑은 고딕", 10, "bold"), bg="#4CAF50", fg="white", padx=10, pady=5)
        btn_folder.pack(side=tk.LEFT, padx=5)

        btn_test = tk.Button(top_frame, text="2. 선택 영역 숫자 테스트", command=self.test_ocr, font=("맑은 고딕", 10, "bold"), bg="#2196F3", fg="white", padx=10, pady=5)
        btn_test.pack(side=tk.LEFT, padx=5)

        btn_run = tk.Button(top_frame, text="3. 전체 파일명 일괄 변경 실행", command=self.rename_all_files, font=("맑은 고딕", 10, "bold"), bg="#FF5722", fg="white", padx=10, pady=5)
        btn_run.pack(side=tk.LEFT, padx=5)

        # 안내 및 상태 표시줄
        self.status_label = tk.Label(self.root, text="먼저 [1. PDF 폴더 선택]을 눌러 작업할 폴더를 지정하세요.", font=("맑은 고딕", 11), fg="#333333", pady=5)
        self.status_label.pack()

        # PDF 미리보기 캔버스 (스크롤바 포함)
        canvas_frame = tk.Frame(self.root)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.canvas = tk.Canvas(canvas_frame, bg="#555555", cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 마우스 이벤트 연결 (드래그로 영역 지정)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

        # 하단 로그 창
        self.log_text = tk.Text(self.root, height=8, font=("맑은 고딕", 9), bg="#1e1e1e", fg="#00ff00")
        self.log_text.pack(fill=tk.X, padx=10, pady=5)
        self.log("프로그램 준비 완료. 오프라인 OCR 엔진이 정상 로드되었습니다.")

    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update()

    def select_folder(self):
        folder = filedialog.askdirectory(title="PDF 파일들이 있는 폴더를 선택하세요")
        if not folder:
            return

        self.folder_path = folder
        self.pdf_files = [f for f in os.listdir(folder) if f.lower().endswith(".pdf")]
        self.pdf_files.sort()

        if not self.pdf_files:
            messagebox.showwarning("경고", "선택한 폴더에 PDF 파일이 없습니다.")
            return

        self.log(f"폴더 선택됨: {folder} (총 {len(self.pdf_files)}개의 PDF 발견)")
        self.load_sample_pdf(os.path.join(folder, self.pdf_files[0]))

    def load_sample_pdf(self, pdf_path):
        """PDF 화면 출력 오류를 방지하기 위해 고해상도(200 DPI) RGB 이미지로 안전하게 렌더링"""
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                raise ValueError("빈 PDF 파일입니다.")
            
            page = doc[0]
            # DPI 200으로 선명하게 렌더링 (회전 및 투명도 오류 방지용 alpha=False)
            pix = page.get_pixmap(dpi=200, alpha=False)
            self.sample_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()

            self.display_image_on_canvas()
            self.status_label.config(text=f"샘플 파일: {os.path.basename(pdf_path)} | 마우스로 숫자가 있는 영역을 드래그하세요.")
        except Exception as e:
            messagebox.showerror("PDF 렌더링 오류", f"PDF 화면을 불러오는 중 오류가 발생했습니다:\n{str(e)}")
            self.log(f"[오류] 샘플 PDF 로드 실패: {str(e)}")

    def display_image_on_canvas(self):
        self.root.update()
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        if canvas_w < 100: canvas_w = 880
        if canvas_h < 100: canvas_h = 520

        img_w, img_h = self.sample_image.size
        # 캔버스 크기에 맞게 비율 유지 축소
        self.scale_factor = min(canvas_w / img_w, canvas_h / img_h)
        new_w = int(img_w * self.scale_factor)
        new_h = int(img_h * self.scale_factor)

        resized_img = self.sample_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized_img)

        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
        self.crop_box = None

    def on_mouse_down(self, event):
        if not self.sample_image:
            return
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2)

    def on_mouse_drag(self, event):
        if not self.rect_id:
            return
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)

    def on_mouse_up(self, event):
        if not self.rect_id:
            return
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)

        x1, x2 = sorted([self.start_x, end_x])
        y1, y2 = sorted([self.start_y, end_y])

        # 너무 작게 클릭만 한 경우 무시
        if (x2 - x1) < 5 or (y2 - y1) < 5:
            return

        # 캔버스 좌표를 원본 고해상도 이미지 좌표로 역산
        orig_x1 = int(x1 / self.scale_factor)
        orig_y1 = int(y1 / self.scale_factor)
        orig_x2 = int(x2 / self.scale_factor)
        orig_y2 = int(y2 / self.scale_factor)

        # 이미지 범위 초과 방지
        img_w, img_h = self.sample_image.size
        orig_x1 = max(0, min(orig_x1, img_w))
        orig_y1 = max(0, min(orig_y1, img_h))
        orig_x2 = max(0, min(orig_x2, img_w))
        orig_y2 = max(0, min(orig_y2, img_h))

        self.crop_box = (orig_x1, orig_y1, orig_x2, orig_y2)
        self.log(f"영역 지정 완료 (원본 좌표): {self.crop_box}")

    def extract_numbers_from_pdf(self, pdf_path):
        """지정된 영역을 잘라내어 오프라인 OCR로 숫자 추출"""
        doc = fitz.open(pdf_path)
        page = doc[0]
        pix = page.get_pixmap(dpi=200, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()

        # 지정한 영역 자르기 (여백을 살짝 주어 인식률 극대화)
        x1, y1, x2, y2 = self.crop_box
        cropped = img.crop((x1, y1, x2, y2))

        # OCR 실행 (PIL 이미지를 numpy 배열로 변환하여 전달)
        import numpy as np
        img_np = np.array(cropped)
        result, _ = self.ocr(img_np)

        if not result:
            return ""

        # 인식된 모든 텍스트 합치기
        raw_text = "".join([line[1] for line in result])
        # 숫자만 추출 (필요시 하이픈(-) 등을 포함하려면 r'[^0-9-]' 로 변경 가능)
        numbers_only = re.sub(r'[^0-9]', '', raw_text)
        return numbers_only

    def test_ocr(self):
        if not self.crop_box:
            messagebox.showwarning("알림", "먼저 화면에서 마우스로 숫자가 있는 영역을 드래그해주세요.")
            return

        sample_path = os.path.join(self.folder_path, self.pdf_files[0])
        self.log("샘플 파일에서 숫자 인식 테스트 중...")
        try:
            detected_num = self.extract_numbers_from_pdf(sample_path)
            if detected_num:
                messagebox.showinfo("인식 성공", f"인식된 숫자: [{detected_num}]\n\n변경될 파일명 예시: {detected_num}.pdf")
                self.log(f"[테스트 성공] 인식된 숫자: {detected_num}")
            else:
                messagebox.showwarning("인식 실패", "해당 영역에서 숫자를 찾지 못했습니다.\n영역을 조금 더 넓게 다시 드래그해보세요.")
                self.log("[테스트 실패] 숫자가 인식되지 않았습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"테스트 중 오류 발생: {str(e)}")

    def rename_all_files(self):
        if not self.crop_box:
            messagebox.showwarning("알림", "먼저 마우스로 숫자가 있는 영역을 드래그해주세요.")
            return

        confirm = messagebox.askyesno("일괄 변경 확인", f"총 {len(self.pdf_files)}개의 PDF 파일명을 지정된 영역의 숫자로 변경하시겠습니까?")
        if not confirm:
            return

        success_count = 0
        fail_count = 0

        for filename in self.pdf_files:
            old_path = os.path.join(self.folder_path, filename)
            try:
                num = self.extract_numbers_from_pdf(old_path)
                if not num:
                    self.log(f"[건너뜀] {filename} -> 숫자를 인식하지 못함")
                    fail_count += 1
                    continue

                # 파일명 중복 방지 처리 (예: 12345.pdf 가 이미 있으면 12345_1.pdf)
                new_filename = f"{num}.pdf"
                new_path = os.path.join(self.folder_path, new_filename)
                counter = 1
                while os.path.exists(new_path) and old_path != new_path:
                    new_filename = f"{num}_{counter}.pdf"
                    new_path = os.path.join(self.folder_path, new_filename)
                    counter += 1

                os.rename(old_path, new_path)
                self.log(f"[성공] {filename} ➔ {new_filename}")
                success_count += 1

            except Exception as e:
                self.log(f"[오류] {filename} 처리 실패: {str(e)}")
                fail_count += 1

        messagebox.showinfo("작업 완료", f"모든 작업이 완료되었습니다!\n\n성공: {success_count}건\n실패(건너뜀): {fail_count}건")
        # 목록 새로고침
        self.select_folder()

if __name__ == "__main__":
    root = tk.Tk()
    app = PDFRenamerApp(root)
    root.mainloop()
