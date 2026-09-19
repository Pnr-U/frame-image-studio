"""Local image resizing with an English desktop interface."""
from pathlib import Path
from PIL import Image, ImageOps

TEXT = {
    'English': {
        'title': 'Frame', 'subtitle': 'Resize locally and save a new image.',
        'choose': '1. Choose image',
        'width': 'Width (px)', 'height': 'Height (px)',
        'lock': 'Keep aspect ratio',
        'hint': 'Exact canvas size: fit the full image and add white padding. No crop.',
        'save': '2. Resize and save as', 'empty': 'Choose an image to get started.',
        'original': 'Original: {} × {} px', 'saved': 'Saved: {} × {} px',
        'error': 'Error', 'done': 'Done', 'select': 'Please choose an image first.',
        'dimensions': 'Width and height must be whole numbers from 1 to 10000.',
        'same': 'Choose a new filename. The original cannot be overwritten.',
        'large': 'Output is too large. Choose smaller dimensions (max. 40 megapixels).',
        'success': 'Image saved:\n{}\n\n{} × {} pixels',
        'images': 'Images', 'all': 'All files',
    },

}


def linked_dimensions(size, value, axis):
    """Calculate the other dimension from the oriented source ratio."""
    w, h = size
    return (value, max(1, round(value * h / w))) if axis == 'width' else (max(1, round(value * w / h)), value)


def compose_image(im, size, mode='Fit', centering=(0.5, 0.5), zoom=1.0, background='#ffffff'):
    if mode == 'Crop':
        ratio = size[0] / size[1]
        cw = min(im.width, im.height * ratio) / max(1.0, zoom)
        ch = cw / ratio
        left = (im.width - cw) * centering[0]
        top = (im.height - ch) * centering[1]
        return im.resize(size, Image.Resampling.LANCZOS, box=(left, top, left + cw, top + ch))
    fitted = ImageOps.contain(im, size, Image.Resampling.LANCZOS)
    canvas = Image.new(im.mode, size, background)
    canvas.paste(fitted, ((size[0] - fitted.width) // 2,
                          (size[1] - fitted.height) // 2))
    return canvas


def resize_image(source, destination, width, height=None, mode='Fit', centering=(0.5, 0.5), zoom=1.0, background='#ffffff', quality=95):
    if not 1 <= width <= 10000 or (height is not None and not 1 <= height <= 10000):
        raise ValueError('dimensions')
    if Path(source).resolve() == Path(destination).resolve():
        raise ValueError('same')
    with Image.open(source) as original:
        im = ImageOps.exif_transpose(original)
        if height is None:
            _, height = linked_dimensions(im.size, width, 'width')
        if not 1 <= height <= 10000:
            raise ValueError('dimensions')
        if width * height > 40_000_000:
            raise ValueError('large')
        im = im.convert('RGBA' if 'A' in im.getbands() or 'transparency' in im.info else 'RGB')
        im = compose_image(im, (width, height), mode, centering, zoom, background)
        suffix = Path(destination).suffix.lower()
        if suffix in ('.jpg', '.jpeg'):
            flattened = Image.new('RGB', im.size, background)
            flattened.paste(im, mask=im.getchannel('A') if im.mode == 'RGBA' else None)
            im = flattened
        options = {'icc_profile': original.info['icc_profile']} if original.info.get('icc_profile') else {}
        if suffix in ('.jpg', '.jpeg', '.webp'):
            options['quality'] = max(1, min(100, int(quality)))
        im.save(destination, **options)
        return im.size


class App:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk
        self.root = root
        root.geometry('1160x780')
        root.minsize(980, 720)
        root.configure(bg='#f6f5f2')
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10), background='#f6f5f2', foreground='#252332')
        style.configure('TButton', padding=(14, 9), background='#ffffff', borderwidth=0)
        style.map('TButton', background=[('active', '#ece9f5')])
        style.configure('Accent.TButton', background='#6d4aff', foreground='white', padding=(18, 12), font=('Segoe UI', 11, 'bold'))
        style.map('Accent.TButton', background=[('active', '#5737d6'), ('disabled', '#c8bedf')])
        style.configure('TEntry', padding=7, fieldbackground='white')
        style.configure('TCombobox', padding=6, fieldbackground='white')
        style.configure('Muted.TLabel', foreground='#777383')
        self.preview_source = None
        self.preview_job = None
        self.center = [0.5, 0.5]
        self.mode = tk.StringVar(value='Fit')
        self.source = tk.StringVar()
        self.width = tk.StringVar(value='1200')
        self.height = tk.StringVar(value='1200')
        self.lock = tk.BooleanVar(value=False)
        self.zoom = tk.DoubleVar(value=1.0)
        self.background = '#ffffff'
        self.quality = tk.DoubleVar(value=95)
        self.format = tk.StringVar(value='JPEG')
        self.preset = tk.StringVar(value='Square · 1200 × 1200')
        self.size = None
        self.busy = False
        self.last_axis = 'width'
        self.status_key, self.status_args = 'empty', ()
        self.labels = []
        head = ttk.Frame(root, padding=(24, 16))
        head.pack(fill='x')
        ttk.Label(head, text='frame', font=('Segoe UI', 26, 'bold')).pack(side='left')
        ttk.Label(head, text='IMAGE STUDIO', style='Muted.TLabel').pack(side='left', padx=18)
        ttk.Button(head, text='Choose image', command=self.choose).pack(side='right')
        ttk.Label(head, text='Local processing · Your images stay on your device', style='Muted.TLabel').pack(side='right', padx=18)
        ttk.Separator(root).pack(fill='x')
        body = ttk.Frame(root, padding=(24, 16))
        body.pack(fill='both', expand=True)
        side = ttk.Frame(body, width=290, padding=(20, 0, 0))
        side.pack(side='right', fill='y')
        side.pack_propagate(False)
        stage = ttk.Frame(body)
        stage.pack(side='left', fill='both', expand=True)
        top = ttk.Frame(stage)
        top.pack(fill='x', pady=(0, 12))
        ttk.Label(top, text='Your canvas', font=('Segoe UI', 16, 'bold')).pack(side='left')
        ttk.Button(top, text='Reset', command=self.reset_all).pack(side='right')
        self.canvas = tk.Canvas(stage, bg='#ebe9e5', highlightthickness=0, cursor='hand2')
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda _: self.queue_preview())
        self.canvas.bind('<ButtonPress-1>', self.begin_drag)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.preview_label = ttk.Label(stage, text='Choose an image to begin', style='Muted.TLabel', wraplength=600)
        self.preview_label.pack(anchor='w', pady=(12, 4))
        self.status = ttk.Label(stage, style='Muted.TLabel', wraplength=600)
        self.status.pack(anchor='w')
        def section(label):
            ttk.Label(side, text=label, font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(8, 5))
        section('CANVAS SIZE')
        presets = ['Square · 1200 × 1200', 'Portrait · 1080 × 1350', 'Story · 1080 × 1920', 'Landscape · 1920 × 1080', 'Original', 'Custom']
        box = ttk.Combobox(side, textvariable=self.preset, values=presets, state='readonly')
        box.pack(fill='x'); box.bind('<<ComboboxSelected>>', self.apply_preset)
        row = ttk.Frame(side); row.pack(fill='x', pady=10)
        for col, (label, var) in enumerate([('Width', self.width), ('Height', self.height)]):
            ttk.Label(row, text=label, style='Muted.TLabel').grid(row=0, column=col, sticky='w')
            ttk.Entry(row, textvariable=var, width=10).grid(row=1, column=col, padx=(0, 10), pady=4)
        ttk.Checkbutton(side, text='Link dimensions', variable=self.lock, command=lambda: self.sync(self.last_axis)).pack(anchor='w')
        section('COMPOSITION')
        modes = ttk.Frame(side); modes.pack(fill='x')
        for value in ('Fit', 'Crop'):
            ttk.Radiobutton(modes, text=value, variable=self.mode, value=value, command=self.change_mode).pack(side='left', padx=(0, 24))
        ttk.Label(side, text='Fit keeps every edge. Crop fills the canvas.\nDrag the preview to reposition in Crop.', style='Muted.TLabel').pack(anchor='w', pady=6)
        self.zoom_label = ttk.Label(side, text='Zoom · 100%', style='Muted.TLabel')
        self.zoom_label.pack(anchor='w')
        ttk.Scale(side, from_=1, to=3, variable=self.zoom, command=self.change_zoom).pack(fill='x')
        ttk.Button(side, text='Center image', command=self.reset_center).pack(anchor='w', pady=5)
        self.color_button = ttk.Button(side, text='Background  #FFFFFF', command=self.pick_color)
        self.color_button.pack(fill='x', pady=5)
        section('EXPORT')
        formats = ttk.Combobox(side, textvariable=self.format, values=['JPEG', 'PNG', 'WebP'], state='readonly')
        formats.pack(fill='x'); formats.bind('<<ComboboxSelected>>', lambda _: self.queue_preview())
        self.quality_label = ttk.Label(side, text='Quality 95 · JPEG / WebP', style='Muted.TLabel')
        self.quality_label.pack(anchor='w', pady=(8, 0))
        ttk.Scale(side, from_=30, to=100, variable=self.quality, command=lambda _: self.quality_label.configure(text=f'Quality {round(self.quality.get())} · JPEG / WebP')).pack(fill='x')
        self.export_button = ttk.Button(side, text='Export image', style='Accent.TButton', command=self.save, state='disabled')
        self.export_button.pack(fill='x', pady=(16, 6))
        ttk.Label(side, text='Original file is always preserved.', style='Muted.TLabel').pack(anchor='w')
        self.width.trace_add('write', lambda *_: self.sync('width'))
        self.height.trace_add('write', lambda *_: self.sync('height'))
        self.width.trace_add('write', lambda *_: self.queue_preview())
        self.height.trace_add('write', lambda *_: self.queue_preview())
        self.refresh_text()
        self.queue_preview()

    def change_zoom(self, value=None):
        # Zooming fills the canvas and intentionally crops the outer edges.
        self.mode.set('Crop')
        self.zoom_label.configure(text=f'Zoom · {round(self.zoom.get() * 100)}%')
        self.queue_preview()

    def change_mode(self):
        if self.mode.get() == 'Fit':
            self.zoom.set(1.0)
            self.zoom_label.configure(text='Zoom · 100%')
        self.queue_preview()

    def pick_color(self):
        from tkinter import colorchooser
        color = colorchooser.askcolor(self.background, title='Choose background color')[1]
        if color:
            self.background = color
            self.color_button.configure(text='Background  ' + color.upper())
            self.queue_preview()

    def apply_preset(self, event=None):
        sizes = {'Square · 1200 × 1200': (1200,1200), 'Portrait · 1080 × 1350': (1080,1350),
                 'Story · 1080 × 1920': (1080,1920), 'Landscape · 1920 × 1080': (1920,1080), 'Original': self.size}
        selected = self.preset.get()
        value = sizes.get(selected)
        if value:
            self.lock.set(False)
            self.width.set(str(value[0])); self.height.set(str(value[1]))
            self.preset.set(selected)
            self.queue_preview()

    def reset_all(self):
        self.lock.set(False)
        self.width.set('1200'); self.height.set('1200')
        self.preset.set('Square · 1200 × 1200')
        self.zoom.set(1.0); self.mode.set('Fit')
        self.zoom_label.configure(text='Zoom · 100%')
        self.background = '#ffffff'
        self.color_button.configure(text='Background  #FFFFFF')
        self.quality.set(95); self.format.set('JPEG')
        self.quality_label.configure(text='Quality 95 · JPEG / WebP')
        self.reset_center()

    def text(self, key):
        return TEXT['English'][key]

    def add(self, widget, key):
        self.labels.append((widget, key))
        return widget

    def refresh_text(self):
        self.root.title('Frame — Image Studio')
        for widget, key in self.labels:
            widget.configure(text=self.text(key))
        self.status.configure(text=self.text(self.status_key).format(*self.status_args))

    def sync(self, axis):
        if self.busy:
            return
        self.preset.set('Custom')
        self.last_axis = axis
        if not self.lock.get() or not self.size:
            return
        try:
            value = int((self.width if axis == 'width' else self.height).get())
            if not 1 <= value <= 10000:
                return
        except ValueError:
            return
        w, h = linked_dimensions(self.size, value, axis)
        self.busy = True
        try:
            (self.height if axis == 'width' else self.width).set(str(h if axis == 'width' else w))
        finally:
            self.busy = False

    def queue_preview(self):
        if self.preview_job:
            self.root.after_cancel(self.preview_job)
        self.preview_job = self.root.after(70, self.update_preview)

    def update_preview(self):
        from PIL import ImageTk
        self.preview_job = None
        self.canvas.delete('all')
        if self.preview_source is None:
            cx, cy = self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2
            self.canvas.create_text(cx, cy - 40, text='A better frame for every image.', font=('Segoe UI', 22, 'bold'), fill='#35313e', width=max(100, self.canvas.winfo_width()-80))
            self.canvas.create_text(cx, cy + 22, text='Click to choose an image', font=('Segoe UI', 13), fill='#6d4aff')
            self.canvas.create_text(cx, cy + 60, text='JPEG  ·  PNG  ·  WebP', font=('Segoe UI', 10), fill='#817a87')
            return
        try:
            w, h = int(self.width.get()), int(self.height.get())
            if not (1 <= w <= 10000 and 1 <= h <= 10000) or w * h > 40_000_000:
                raise ValueError
        except ValueError:
            self.preview_label.configure(text='Enter valid dimensions to preview.')
            return
        available_w = max(1, self.canvas.winfo_width() - 24)
        available_h = max(1, self.canvas.winfo_height() - 24)
        scale = min(available_w / w, available_h / h)
        pw, ph = max(1, round(w * scale)), max(1, round(h * scale))
        frame = compose_image(self.preview_source, (pw, ph), self.mode.get(), tuple(self.center), self.zoom.get(), self.background)
        white = Image.new('RGBA', frame.size, self.background if self.format.get() == 'JPEG' else '#ffffff')
        white.alpha_composite(frame)
        self.preview_photo = ImageTk.PhotoImage(white.convert('RGB'))
        self.canvas.create_image(self.canvas.winfo_width() // 2,
                                 self.canvas.winfo_height() // 2, image=self.preview_photo)
        self.preview_label.configure(text=f'Preview: {w} × {h} px | {self.mode.get()} | Export uses the original image')
        if self.size:
            effective_zoom = self.zoom.get() if self.mode.get() == 'Crop' else 1
            factor = (max if self.mode.get() == 'Crop' else min)(w / self.size[0], h / self.size[1]) * effective_zoom
            if factor > 1.01:
                self.preview_label.configure(text=f'{w} × {h} px · Enlarging {factor:.1f}× — detail may soften')
        self.preview_size = (pw, ph)

    def reset_center(self):
        self.center = [0.5, 0.5]
        self.queue_preview()

    def begin_drag(self, event):
        if self.preview_source is None:
            self.choose()
            return
        self.drag_start = (event.x, event.y, tuple(self.center))

    def drag(self, event):
        if self.mode.get() != 'Crop' or self.preview_source is None or not hasattr(self, 'drag_start') or not hasattr(self, 'preview_size'):
            return
        pw, ph = self.preview_size
        iw, ih = self.preview_source.size
        scale = max(pw / iw, ph / ih) * self.zoom.get()
        overflow = (iw * scale - pw, ih * scale - ph)
        x, y, center = self.drag_start
        for axis, movement in enumerate((event.x - x, event.y - y)):
            if overflow[axis] > 0.5:
                self.center[axis] = max(0.0, min(1.0, center[axis] - movement / overflow[axis]))
        self.queue_preview()

    def choose(self):
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(title=self.text('choose'), filetypes=[(self.text('images'), '*.jpg *.jpeg *.png *.webp'), (self.text('all'), '*.*')])
        if not path:
            return
        try:
            with Image.open(path) as im:
                oriented = ImageOps.exif_transpose(im)
                self.size = oriented.size
                self.preview_source = oriented.convert('RGBA')
                self.preview_source.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            self.center = [0.5, 0.5]
            self.source.set(path)
            self.export_button.configure(state='normal')
            if self.preset.get() == 'Original':
                self.apply_preset()
            self.sync(self.last_axis)
            self.queue_preview()
            self.status_key, self.status_args = 'original', self.size
            self.refresh_text()
        except Exception as exc:
            messagebox.showerror(self.text('error'), str(exc))

    def save(self):
        from tkinter import filedialog, messagebox
        if not self.source.get():
            messagebox.showinfo(self.text('title'), self.text('select'))
            return
        try:
            w, h = int(self.width.get()), int(self.height.get())
            if not (1 <= w <= 10000 and 1 <= h <= 10000):
                raise ValueError
        except ValueError:
            messagebox.showerror(self.text('error'), self.text('dimensions'))
            return
        if w * h > 40_000_000:
            messagebox.showerror(self.text('error'), self.text('large'))
            return
        ext = {'JPEG': '.jpg', 'PNG': '.png', 'WebP': '.webp'}[self.format.get()]
        dest = filedialog.asksaveasfilename(title='Export image', initialfile=f'{Path(self.source.get()).stem}_{w}x{h}{ext}', defaultextension=ext, filetypes=[(self.format.get(), '*' + ext)])
        if dest:
            try:
                result = resize_image(self.source.get(), dest, w, h, self.mode.get(), tuple(self.center), self.zoom.get(), self.background, round(self.quality.get()))
                self.status_key, self.status_args = 'saved', result
                self.refresh_text()
                messagebox.showinfo(self.text('done'), self.text('success').format(dest, *result))
            except Exception as exc:
                messagebox.showerror(self.text('error'), TEXT['English'].get(str(exc), str(exc)))


def main():
    import tkinter as tk
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
