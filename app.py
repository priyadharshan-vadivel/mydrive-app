from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
import sqlite3
import os
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# ✅ Use /tmp for Vercel (only writable directory)
UPLOAD_FOLDER = '/tmp/uploads'
DATABASE = '/tmp/database.db'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            upload_time TEXT NOT NULL,
            file_size INTEGER
        )
    ''')
    conn.commit()
    conn.close()


# ✅ Run init on every cold start (required for serverless)
init_db()


@app.route('/')
def index():
    try:
        conn = get_db()
        images = conn.execute('SELECT * FROM images ORDER BY upload_time DESC').fetchall()
        conn.close()
    except Exception:
        images = []
    return render_template('index.html', images=images)


@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        if 'file' not in request.files:
            flash('No file selected.', 'error')
            return redirect(url_for('index'))

        file = request.files['file']

        if file.filename == '':
            flash('No file selected.', 'error')
            return redirect(url_for('index'))

        if file and allowed_file(file.filename):
            original_name = file.filename
            filename = secure_filename(file.filename)

            if not filename:
                flash('Invalid filename.', 'error')
                return redirect(url_for('index'))

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
            filename = timestamp + filename
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)

            file_size = os.path.getsize(file_path)
            upload_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            conn = get_db()
            conn.execute(
                'INSERT INTO images (filename, original_name, file_path, upload_time, file_size) VALUES (?, ?, ?, ?, ?)',
                (filename, original_name, file_path, upload_time, file_size)
            )
            conn.commit()
            conn.close()

            flash(f'"{original_name}" uploaded successfully!', 'success')
        else:
            flash('Invalid file type. Only JPG, JPEG, PNG allowed.', 'error')

    except PermissionError as e:
        flash(f'Permission error: {str(e)}', 'error')
    except Exception as e:
        flash(f'Upload failed: {str(e)}', 'error')

    return redirect(url_for('index'))


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route('/delete/<int:image_id>', methods=['POST'])
def delete_image(image_id):
    try:
        conn = get_db()
        image = conn.execute('SELECT * FROM images WHERE id = ?', (image_id,)).fetchone()
        if image:
            if os.path.exists(image['file_path']):
                os.remove(image['file_path'])
            conn.execute('DELETE FROM images WHERE id = ?', (image_id,))
            conn.commit()
            flash(f'"{image["original_name"]}" deleted.', 'success')
        conn.close()
    except Exception as e:
        flash(f'Delete failed: {str(e)}', 'error')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)