#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import os
import math
import platform
from PIL import Image, ImageFont, ImageDraw, ImageEnhance, ImageChops, ImageOps
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QFileDialog, QSpinBox, 
                             QDoubleSpinBox, QComboBox, QGroupBox, QCheckBox, QProgressBar,
                             QMessageBox, QTextEdit, QSlider, QColorDialog, QTabWidget,
                             QRadioButton, QButtonGroup)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPalette

class WatermarkThread(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, file_paths, mark_type, text_mark, image_mark_path, output_dir, 
                 color, space, angle, font_family, font_height_crop, size, opacity, 
                 quality, image_scale, image_opacity):
        super().__init__()
        self.file_paths = file_paths
        self.mark_type = mark_type  # 'text' 或 'image'
        self.text_mark = text_mark
        self.image_mark_path = image_mark_path
        self.output_dir = output_dir
        self.color = color
        self.space = space
        self.angle = angle
        self.font_family = font_family
        self.font_height_crop = font_height_crop
        self.size = size
        self.opacity = opacity
        self.quality = quality
        self.image_scale = image_scale
        self.image_opacity = image_opacity
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            if self.mark_type == 'text':
                mark_func = self.gen_text_mark()
            else:
                mark_func = self.gen_image_mark()
                
            total = len(self.file_paths)
            
            for i, image_path in enumerate(self.file_paths):
                if not self._is_running:
                    break
                    
                try:
                    self.process_image(image_path, mark_func)
                    progress = int((i + 1) / total * 100)
                    self.progress.emit(progress)
                except Exception as e:
                    self.log.emit(f"错误: {os.path.basename(image_path)} - {str(e)}")
            
            self.log.emit("处理完成！")
            self.finished.emit()
            
        except Exception as e:
            self.log.emit(f"处理过程中发生错误: {str(e)}")
            self.finished.emit()

    def process_image(self, imagePath, mark):
        im = Image.open(imagePath)
        im = ImageOps.exif_transpose(im)

        image = mark(im)
        name = os.path.basename(imagePath)
        if image:
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)

            new_name = os.path.join(self.output_dir, name)
            if os.path.splitext(new_name)[1] != '.png':
                image = image.convert('RGB')
            image.save(new_name, quality=self.quality)
            self.log.emit(f"✓ {name} - 成功")
        else:
            self.log.emit(f"✗ {name} - 失败")

    def set_opacity(self, im, opacity):
        assert opacity >= 0 and opacity <= 1
        if im.mode != 'RGBA':
            im = im.convert('RGBA')
        alpha = im.split()[3]
        alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
        im.putalpha(alpha)
        return im

    def crop_image(self, im):
        bg = Image.new(mode='RGBA', size=im.size)
        diff = ImageChops.difference(im, bg)
        del bg
        bbox = diff.getbbox()
        if bbox:
            return im.crop(bbox)
        return im

    def get_default_font(self):
        """获取系统默认字体"""
        system = platform.system()
        if system == "Darwin":  # macOS
            mac_fonts = [
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "/Library/Fonts/Arial.ttf"
            ]
            for font_path in mac_fonts:
                if os.path.exists(font_path):
                    return font_path
        elif system == "Windows":
            win_fonts = [
                "C:/Windows/Fonts/simhei.ttf",
                "C:/Windows/Fonts/msyh.ttc",
                "C:/Windows/Fonts/arial.ttf"
            ]
            for font_path in win_fonts:
                if os.path.exists(font_path):
                    return font_path
        else:
            linux_fonts = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
            ]
            for font_path in linux_fonts:
                if os.path.exists(font_path):
                    return font_path
        return None

    def gen_text_mark(self):
        """生成文字水印"""
        is_height_crop_float = '.' in self.font_height_crop
        width = len(self.text_mark) * self.size
        if is_height_crop_float:
            height = round(self.size * float(self.font_height_crop))
        else:
            height = int(self.font_height_crop)

        mark = Image.new(mode='RGBA', size=(width, height))
        draw_table = ImageDraw.Draw(im=mark)
        
        # 字体处理
        font = None
        if self.font_family and os.path.exists(self.font_family):
            try:
                font = ImageFont.truetype(self.font_family, size=self.size)
            except:
                self.log.emit(f"警告: 无法加载字体 {self.font_family}，使用系统默认字体")
        
        if font is None:
            default_font = self.get_default_font()
            if default_font and os.path.exists(default_font):
                try:
                    font = ImageFont.truetype(default_font, size=self.size)
                except:
                    pass
        
        if font is None:
            try:
                font = ImageFont.load_default()
            except:
                self.log.emit("警告: 使用默认字体失败")

        draw_table.text(xy=(0, 0),
                        text=self.text_mark,
                        fill=self.color,
                        font=font)
        del draw_table

        mark = self.crop_image(mark)
        mark = self.set_opacity(mark, self.opacity)

        def mark_im(im):
            c = int(math.sqrt(im.size[0] * im.size[0] + im.size[1] * im.size[1]))
            mark2 = Image.new(mode='RGBA', size=(c, c))

            y, idx = 0, 0
            while y < c:
                x = -int((mark.size[0] + self.space) * 0.5 * idx)
                idx = (idx + 1) % 2

                while x < c:
                    mark2.paste(mark, (x, y))
                    x = x + mark.size[0] + self.space
                y = y + mark.size[1] + self.space

            mark2 = mark2.rotate(self.angle)

            if im.mode != 'RGBA':
                im = im.convert('RGBA')
            im.paste(mark2, 
                    (int((im.size[0] - c) / 2), int((im.size[1] - c) / 2)),
                    mask=mark2.split()[3])
            del mark2
            return im

        return mark_im

    def gen_image_mark(self):
        """生成图片水印"""
        if not self.image_mark_path or not os.path.exists(self.image_mark_path):
            raise Exception("图片水印文件不存在")
        
        # 加载水印图片
        mark_img = Image.open(self.image_mark_path)
        
        # 转换为RGBA模式
        if mark_img.mode != 'RGBA':
            mark_img = mark_img.convert('RGBA')
        
        # 调整图片大小
        base_size = 100  # 基准大小
        scale_factor = self.image_scale / 100.0
        new_width = int(mark_img.width * scale_factor)
        new_height = int(mark_img.height * scale_factor)
        mark_img = mark_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # 设置透明度
        mark_img = self.set_opacity(mark_img, self.image_opacity / 100.0)

        def mark_im(im):
            c = int(math.sqrt(im.size[0] * im.size[0] + im.size[1] * im.size[1]))
            mark2 = Image.new(mode='RGBA', size=(c, c))

            y, idx = 0, 0
            while y < c:
                x = -int((mark_img.size[0] + self.space) * 0.5 * idx)
                idx = (idx + 1) % 2

                while x < c:
                    mark2.paste(mark_img, (x, y))
                    x = x + mark_img.size[0] + self.space
                y = y + mark_img.size[1] + self.space

            mark2 = mark2.rotate(self.angle)

            if im.mode != 'RGBA':
                im = im.convert('RGBA')
            im.paste(mark2, 
                    (int((im.size[0] - c) / 2), int((im.size[1] - c) / 2)),
                    mask=mark2.split()[3])
            del mark2
            return im

        return mark_im


class WatermarkApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.watermark_thread = None

    def init_ui(self):
        self.setWindowTitle("图片水印添加工具 - 支持文字和图片水印")
        self.setFixedSize(750, 850)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 显示系统信息
        system_info = QLabel(f"运行系统: {platform.system()} {platform.release()}")
        system_info.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(system_info)

        # 创建标签页
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # 基本设置标签页
        basic_tab = QWidget()
        tabs.addTab(basic_tab, "基本设置")
        self.setup_basic_tab(basic_tab)

        # 高级设置标签页
        advanced_tab = QWidget()
        tabs.addTab(advanced_tab, "高级设置")
        self.setup_advanced_tab(advanced_tab)

        # 进度和日志
        self.setup_progress_log(layout)

    def setup_basic_tab(self, tab):
        layout = QVBoxLayout(tab)

        # 文件选择
        file_group = QGroupBox("文件设置")
        file_layout = QVBoxLayout(file_group)

        # 输入文件
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("输入文件/文件夹:"))
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText("选择图片文件或文件夹")
        input_layout.addWidget(self.input_path)
        self.input_btn = QPushButton("浏览")
        self.input_btn.clicked.connect(self.select_input)
        input_layout.addWidget(self.input_btn)
        file_layout.addLayout(input_layout)

        # 输出目录
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("输出目录:"))
        self.output_path = QLineEdit("./output")
        output_layout.addWidget(self.output_path)
        self.output_btn = QPushButton("浏览")
        self.output_btn.clicked.connect(self.select_output)
        output_layout.addWidget(self.output_btn)
        file_layout.addLayout(output_layout)

        layout.addWidget(file_group)

        # 水印类型选择
        type_group = QGroupBox("水印类型")
        type_layout = QVBoxLayout(type_group)
        
        self.watermark_type_group = QButtonGroup()
        
        text_radio_layout = QHBoxLayout()
        self.text_radio = QRadioButton("文字水印")
        self.text_radio.setChecked(True)
        self.watermark_type_group.addButton(self.text_radio)
        text_radio_layout.addWidget(self.text_radio)
        text_radio_layout.addStretch()
        type_layout.addLayout(text_radio_layout)
        
        image_radio_layout = QHBoxLayout()
        self.image_radio = QRadioButton("图片水印")
        self.watermark_type_group.addButton(self.image_radio)
        image_radio_layout.addWidget(self.image_radio)
        image_radio_layout.addStretch()
        type_layout.addLayout(image_radio_layout)
        
        # 连接信号
        self.text_radio.toggled.connect(self.on_watermark_type_changed)
        
        layout.addWidget(type_group)

        # 文字水印设置
        self.text_mark_group = QGroupBox("文字水印设置")
        text_mark_layout = QVBoxLayout(self.text_mark_group)
        
        # 水印内容
        mark_layout = QHBoxLayout()
        mark_layout.addWidget(QLabel("水印文字:"))
        self.mark_text = QLineEdit()
        self.mark_text.setPlaceholderText("输入水印文字，例如：版权所有")
        mark_layout.addWidget(self.mark_text)
        text_mark_layout.addLayout(mark_layout)

        # 颜色选择
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("文字颜色:"))
        self.color_edit = QLineEdit("#8B8B1B")
        color_layout.addWidget(self.color_edit)
        self.color_btn = QPushButton("选择颜色")
        self.color_btn.clicked.connect(self.select_color)
        color_layout.addWidget(self.color_btn)
        
        # 颜色预览
        self.color_preview = QLabel("    ")
        self.color_preview.setStyleSheet("background-color: #8B8B1B; border: 1px solid black;")
        self.color_preview.setFixedSize(30, 20)
        color_layout.addWidget(self.color_preview)
        text_mark_layout.addLayout(color_layout)
        
        layout.addWidget(self.text_mark_group)

        # 图片水印设置
        self.image_mark_group = QGroupBox("图片水印设置")
        self.image_mark_group.setVisible(False)  # 默认隐藏
        image_mark_layout = QVBoxLayout(self.image_mark_group)
        
        # 图片选择
        image_select_layout = QHBoxLayout()
        image_select_layout.addWidget(QLabel("水印图片:"))
        self.image_mark_path = QLineEdit()
        self.image_mark_path.setPlaceholderText("选择水印图片文件")
        image_select_layout.addWidget(self.image_mark_path)
        self.image_mark_btn = QPushButton("浏览")
        self.image_mark_btn.clicked.connect(self.select_image_mark)
        image_select_layout.addWidget(self.image_mark_btn)
        image_mark_layout.addLayout(image_select_layout)
        
        # 图片预览
        self.image_preview_label = QLabel("预览: 未选择图片")
        self.image_preview_label.setStyleSheet("border: 1px solid gray; padding: 5px;")
        self.image_preview_label.setFixedHeight(60)
        self.image_preview_label.setAlignment(Qt.AlignCenter)
        image_mark_layout.addWidget(self.image_preview_label)
        
        # 图片缩放
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("图片缩放:"))
        self.image_scale_slider = QSlider(Qt.Horizontal)
        self.image_scale_slider.setRange(10, 200)
        self.image_scale_slider.setValue(100)
        scale_layout.addWidget(self.image_scale_slider)
        self.image_scale_label = QLabel("100%")
        self.image_scale_label.setFixedWidth(40)
        scale_layout.addWidget(self.image_scale_label)
        self.image_scale_slider.valueChanged.connect(self.update_image_scale_label)
        image_mark_layout.addLayout(scale_layout)
        
        # 图片透明度
        image_opacity_layout = QHBoxLayout()
        image_opacity_layout.addWidget(QLabel("图片透明度:"))
        self.image_opacity_slider = QSlider(Qt.Horizontal)
        self.image_opacity_slider.setRange(1, 100)
        self.image_opacity_slider.setValue(50)
        image_opacity_layout.addWidget(self.image_opacity_slider)
        self.image_opacity_label = QLabel("0.50")
        self.image_opacity_label.setFixedWidth(40)
        image_opacity_layout.addWidget(self.image_opacity_label)
        self.image_opacity_slider.valueChanged.connect(self.update_image_opacity_label)
        image_mark_layout.addLayout(image_opacity_layout)
        
        layout.addWidget(self.image_mark_group)

    def setup_advanced_tab(self, tab):
        layout = QVBoxLayout(tab)

        # 字体设置（仅对文字水印有效）
        self.font_group = QGroupBox("字体设置")
        font_layout = QVBoxLayout(self.font_group)

        # 字体文件
        font_file_layout = QHBoxLayout()
        font_file_layout.addWidget(QLabel("字体文件:"))
        
        system = platform.system()
        if system == "Darwin":
            default_font = "/System/Library/Fonts/PingFang.ttc"
        elif system == "Windows":
            default_font = "C:/Windows/Fonts/simhei.ttf"
        else:
            default_font = ""
            
        self.font_path = QLineEdit(default_font)
        self.font_path.setPlaceholderText("选择字体文件路径或使用系统默认")
        font_file_layout.addWidget(self.font_path)
        self.font_btn = QPushButton("浏览")
        self.font_btn.clicked.connect(self.select_font)
        font_file_layout.addWidget(self.font_btn)
        font_layout.addLayout(font_file_layout)

        # 字体大小
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("字体大小:"))
        self.font_size = QSpinBox()
        self.font_size.setRange(10, 200)
        self.font_size.setValue(50)
        self.font_size.setSuffix(" px")
        size_layout.addWidget(self.font_size)
        size_layout.addStretch()
        font_layout.addLayout(size_layout)

        layout.addWidget(self.font_group)

        # 水印样式（通用设置）
        style_group = QGroupBox("水印样式")
        style_layout = QVBoxLayout(style_group)

        # 透明度（文字水印用）
        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(QLabel("文字透明度:"))
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(1, 100)
        self.opacity_slider.setValue(15)
        opacity_layout.addWidget(self.opacity_slider)
        self.opacity_label = QLabel("0.15")
        self.opacity_label.setFixedWidth(40)
        opacity_layout.addWidget(self.opacity_label)
        self.opacity_slider.valueChanged.connect(self.update_opacity_label)
        style_layout.addLayout(opacity_layout)

        # 旋转角度
        angle_layout = QHBoxLayout()
        angle_layout.addWidget(QLabel("旋转角度:"))
        self.angle_spin = QSpinBox()
        self.angle_spin.setRange(0, 360)
        self.angle_spin.setValue(30)
        self.angle_spin.setSuffix(" °")
        angle_layout.addWidget(self.angle_spin)
        style_layout.addLayout(angle_layout)

        # 水印间距
        space_layout = QHBoxLayout()
        space_layout.addWidget(QLabel("水印间距:"))
        self.space_spin = QSpinBox()
        self.space_spin.setRange(10, 500)
        self.space_spin.setValue(75)
        self.space_spin.setSuffix(" px")
        space_layout.addWidget(self.space_spin)
        style_layout.addLayout(space_layout)

        # 输出质量
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("输出质量:"))
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(80)
        self.quality_spin.setSuffix(" %")
        quality_layout.addWidget(self.quality_spin)
        style_layout.addLayout(quality_layout)

        layout.addWidget(style_group)

    def setup_progress_log(self, layout):
        # 控制按钮
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始处理")
        self.start_btn.clicked.connect(self.start_processing)
        self.start_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        
        self.stop_btn = QPushButton("停止处理")
        self.stop_btn.clicked.connect(self.stop_processing)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # 日志输出
        log_group = QGroupBox("处理日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)

    def on_watermark_type_changed(self, checked):
        """水印类型切换时的处理"""
        if checked:  # 文字水印
            self.text_mark_group.setVisible(True)
            self.image_mark_group.setVisible(False)
            self.font_group.setVisible(True)
        else:  # 图片水印
            self.text_mark_group.setVisible(False)
            self.image_mark_group.setVisible(True)
            self.font_group.setVisible(False)

    def select_input(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "选择图片文件", "", 
                                                 "图片文件 (*.jpg *.jpeg *.png *.bmp *.gif);;所有文件 (*)", 
                                                 options=options)
        if file_path:
            self.input_path.setText(file_path)
        else:
            folder_path = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
            if folder_path:
                self.input_path.setText(folder_path)

    def select_output(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_path.setText(path)

    def select_font(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择字体文件", "", "字体文件 (*.ttf *.ttc *.otf)")
        if path:
            self.font_path.setText(path)

    def select_image_mark(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择水印图片", "", 
                                            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif)")
        if path:
            self.image_mark_path.setText(path)
            # 显示预览信息
            try:
                img = Image.open(path)
                self.image_preview_label.setText(f"预览: {os.path.basename(path)} ({img.width}×{img.height})")
            except:
                self.image_preview_label.setText("预览: 无法加载图片")

    def select_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            color_hex = color.name()
            self.color_edit.setText(color_hex)
            self.color_preview.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")

    def update_opacity_label(self, value):
        opacity = value / 100
        self.opacity_label.setText(f"{opacity:.2f}")

    def update_image_scale_label(self, value):
        self.image_scale_label.setText(f"{value}%")

    def update_image_opacity_label(self, value):
        opacity = value / 100
        self.image_opacity_label.setText(f"{opacity:.2f}")

    def start_processing(self):
        # 验证输入
        if not self.input_path.text() or not os.path.exists(self.input_path.text()):
            QMessageBox.warning(self, "警告", "请输入有效的输入路径")
            return

        # 根据水印类型验证不同的参数
        if self.text_radio.isChecked():
            # 文字水印验证
            if not self.mark_text.text():
                QMessageBox.warning(self, "警告", "请输入水印文字")
                return
            mark_type = 'text'
            image_mark_path = None
        else:
            # 图片水印验证
            if not self.image_mark_path.text() or not os.path.exists(self.image_mark_path.text()):
                QMessageBox.warning(self, "警告", "请选择有效的水印图片")
                return
            mark_type = 'image'
            image_mark_path = self.image_mark_path.text()

        # 获取文件列表
        input_path = self.input_path.text()
        if os.path.isfile(input_path):
            file_paths = [input_path]
        else:
            file_paths = []
            for file in os.listdir(input_path):
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif')):
                    file_paths.append(os.path.join(input_path, file))

        if not file_paths:
            QMessageBox.warning(self, "警告", "未找到图片文件")
            return

        # 创建输出目录
        output_dir = self.output_path.text()
        if not output_dir:
            output_dir = "./output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 禁用开始按钮，启用停止按钮
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.log_text.clear()

        # 启动处理线程
        self.watermark_thread = WatermarkThread(
            file_paths=file_paths,
            mark_type=mark_type,
            text_mark=self.mark_text.text() if mark_type == 'text' else '',
            image_mark_path=image_mark_path,
            output_dir=output_dir,
            color=self.color_edit.text(),
            space=self.space_spin.value(),
            angle=self.angle_spin.value(),
            font_family=self.font_path.text(),
            font_height_crop="1.2",
            size=self.font_size.value(),
            opacity=self.opacity_slider.value() / 100,
            quality=self.quality_spin.value(),
            image_scale=self.image_scale_slider.value(),
            image_opacity=self.image_opacity_slider.value()
        )

        self.watermark_thread.progress.connect(self.progress_bar.setValue)
        self.watermark_thread.log.connect(self.log_text.append)
        self.watermark_thread.finished.connect(self.processing_finished)
        self.watermark_thread.start()

        self.log_text.append("开始处理图片...")
        self.log_text.append(f"找到 {len(file_paths)} 个图片文件")
        self.log_text.append(f"使用{'文字' if mark_type == 'text' else '图片'}水印")

    def stop_processing(self):
        if self.watermark_thread and self.watermark_thread.isRunning():
            self.watermark_thread.stop()
            self.watermark_thread.wait()
            self.log_text.append("处理已停止")

    def processing_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.log_text.append("所有图片处理完成！")
        QMessageBox.information(self, "完成", "所有图片处理完成！")

def main():
    app = QApplication(sys.argv)
    
    system = platform.system()
    if system == "Darwin":
        app.setFont(QFont("PingFang", 12))
    elif system == "Windows":
        app.setFont(QFont("Microsoft YaHei", 10))
    else:
        app.setFont(QFont("Ubuntu", 10))
    
    window = WatermarkApp()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()