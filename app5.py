from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'secret_key_123'
app.config['DATABASE'] = 'izhevsk.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# Создаем папки
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/images', exist_ok=True)


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def init_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()

    # Создаем таблицу пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_admin BOOLEAN DEFAULT 0
        )
    ''')

    # Проверяем, есть ли столбец is_admin, если нет - добавляем
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'is_admin' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0')
        print("Добавлен столбец is_admin в таблицу users")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attractions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            detailed_description TEXT,
            category TEXT,
            address TEXT,
            image TEXT,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            views INTEGER DEFAULT 0,
            rating REAL DEFAULT 0,
            votes INTEGER DEFAULT 0,
            latitude REAL,
            longitude REAL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attraction_id INTEGER,
            user_id INTEGER,
            content TEXT NOT NULL,
            rating INTEGER CHECK(rating >= 1 AND rating <= 5),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (attraction_id) REFERENCES attractions (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attraction_id INTEGER,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(attraction_id, user_id),
            FOREIGN KEY (attraction_id) REFERENCES attractions (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Создаем админа по умолчанию, если его нет
    cursor.execute('SELECT COUNT(*) FROM users WHERE username = ?', ('admin',))
    if cursor.fetchone()[0] == 0:
        try:
            cursor.execute('INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)',
                           ('admin', 'admin123', 1))
            print("Создан пользователь admin с паролем admin123")
        except sqlite3.IntegrityError:
            print("Пользователь admin уже существует")
        except Exception as e:
            print(f"Ошибка при создании админа: {e}")
    else:
        # Обновляем существующего админа
        cursor.execute('UPDATE users SET is_admin = 1 WHERE username = ?', ('admin',))

    # Добавляем ВСЕ оригинальные достопримечательности с оригинальными путями к изображениям
    cursor.execute('SELECT COUNT(*) FROM attractions')
    count = cursor.fetchone()[0]

    if count == 0:
        attractions_data = [
            ('Михайловский собор', 'Главный храм Ижевска с красивой архитектурой',
             'Михайловский собор — величественный православный храм, возведенный в 2007 году на месте одноименного собора...',
             'Архитектура', 'ул. К. Маркса, 222', 'images/sobor.jpg', 1),
            ('Набережная пруда', 'Живописная набережная для прогулок',
             'Набережная Ижевского пруда — одно из самых популярных мест для прогулок и отдыха горожан и гостей города...',
             'Прогулки', 'Набережная пруда', 'images/naberezhnaya.jpg', 1),
            ('Музей Ижмаш', 'История оружейного завода и города',
             'Музей Ижмаш — уникальное учреждение, рассказывающее историю одного из старейших оружейных заводов России...',
             'Музеи', 'ул. Свердлова, 32', 'images/izhmash.jpg', 1),
            ('Парк Космонавтов', 'Парк с аллеей славы космонавтов',
             'Парк Космонавтов — тематический парк, созданный в 1965 году в честь достижений советской космонавтики...',
             'Парки', 'ул. 9 Января, 213', 'images/park.jpg', 1),
            ('Зоопарк', 'Крупный зоопарк с разнообразными животными',
             'Ижевский зоопарк — один из крупнейших и современных зоологических парков в Приволжском федеральном округе...',
             'Развлечения', 'ул. Кирова, 8', 'images/zoo.jpg', 1),
            ('Арсенал', 'Культурный центр с выставками',
             'Арсенал — культурно-выставочный комплекс, расположенный в историческом здании бывшего оружейного арсенала...',
             'Культура', 'ул. Коммунаров, 287', 'images/arsenal.jpg', 1),
            ('Памятник Ижику', 'Символ Ижевска - крокодил Ижик',
             'Памятник Ижику — одна из самых молодых и оригинальных достопримечательностей Ижевска, установленная в 2019 году...',
             'Памятники', 'ул. Советская, 1', 'images/izhik.jpg', 1),
            ('Цирк', 'Стационарный цирк с представлениями',
             'Ижевский государственный цирк — современное здание, построенное в 1999 году на месте старого цирка...',
             'Развлечения', 'ул. Красноармейская, 136', 'images/circus.jpg', 1),
            ('Свято-Троицкий собор', 'Старейший храм Ижевска',
             'Свято-Троицкий собор — старейший православный храм Ижевска, построенный в 1812-1814 годах...',
             'Архитектура', 'ул. Удмуртская, 220', 'images/troitsky.jpg', 1),
            ('Летний сад', 'Старейший парк города',
             'Летний сад имени Горького — старейший парк Ижевска, основанный в 1857 году по инициативе горного начальника завода...',
             'Парки', 'ул. Милиционная, 4', 'images/letniy_sad.jpg', 1),
            ('Памятник крокодилу', 'Необычный памятник в центре города',
             'Памятник крокодилу — еще одно воплощение неофициального символа Ижевска, установленное в 2005 году...',
             'Памятники', 'ул. Советская, 22', 'images/crocodile.jpg', 1),
            ('Национальный музей', 'Музей истории Удмуртской республики',
             'Национальный музей Удмуртской Республики имени Кузебая Герда — крупнейшее музейное учреждение республики...',
             'Музеи', 'ул. Коммунаров, 287', 'images/museum.jpg', 1),
            ('Театр оперы и балета', 'Государственный театр Удмуртии',
             'Государственный театр оперы и балета Удмуртской Республики — ведущая музыкальная сцена региона...',
             'Культура', 'ул. Пушкинская, 221', 'images/teatr.jpg', 1),
            ('Сквер у Вечного огня', 'Мемориальный комплекс',
             'Сквер у Вечного огня — мемориальный комплекс, созданный в 1967 году в память о воинах-удмуртах...',
             'Памятники', 'Центральная площадь', 'images/skver.jpg', 1)
        ]

        try:
            cursor.executemany('''
                INSERT INTO attractions 
                (name, description, detailed_description, category, address, image, user_id, status) 
                VALUES (?,?,?,?,?,?,?,'approved')
            ''', attractions_data)
            print("Добавлены все достопримечательности с оригинальными путями к изображениям")
        except Exception as e:
            print(f"Ошибка при добавлении данных: {e}")

    conn.commit()
    conn.close()


@app.route('/')
def index():
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()

    # Последние добавленные места
    cursor.execute('''
        SELECT a.*, u.username 
        FROM attractions a 
        LEFT JOIN users u ON a.user_id = u.id 
        WHERE a.status = 'approved' 
        ORDER BY a.created_at DESC 
        LIMIT 6
    ''')
    attractions = cursor.fetchall()

    # Самые популярные места
    cursor.execute('''
        SELECT a.*, u.username 
        FROM attractions a 
        LEFT JOIN users u ON a.user_id = u.id 
        WHERE a.status = 'approved' 
        ORDER BY a.views DESC 
        LIMIT 3
    ''')
    popular = cursor.fetchall()

    # Статистика
    cursor.execute('SELECT COUNT(*) FROM attractions WHERE status = "approved"')
    total_places = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM attractions WHERE status = "approved" AND category = "Природа"')
    nature_places = cursor.fetchone()[0]

    conn.close()

    return render_template('index.html',
                           attractions=attractions,
                           popular=popular,
                           total_places=total_places,
                           total_users=total_users,
                           nature_places=nature_places,
                           user=session.get('user'))


@app.route('/add_place', methods=['GET', 'POST'])
def add_place():
    if 'user' not in session:
        flash('Для добавления места необходимо войти в систему!')
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        detailed_description = request.form.get('detailed_description', '').strip()
        category = request.form.get('category', '').strip()
        address = request.form.get('address', '').strip()

        if not all([name, description, detailed_description, category, address]):
            flash('Все поля обязательны для заполнения!')
            return render_template('add_place.html', user=session.get('user'))

        # Обработка изображения
        image = 'images/placeholder.jpg'
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    unique_filename = f"{timestamp}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    file.save(file_path)
                    image = f"uploads/{unique_filename}"
                else:
                    flash('Недопустимый формат файла. Используйте PNG, JPG или JPEG.')
                    return render_template('add_place.html', user=session.get('user'))

        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO attractions 
                (name, description, detailed_description, category, address, image, user_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            ''', (name, description, detailed_description, category, address, image, session['user']['id']))

            conn.commit()
            flash('Место успешно добавлено и ожидает модерации!')
            return redirect(url_for('my_places'))

        except Exception as e:
            flash(f'Ошибка при добавлении места: {str(e)}')
        finally:
            conn.close()

    return render_template('add_place.html', user=session.get('user'))


@app.route('/my_places')
def my_places():
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM attractions 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    ''', (session['user']['id'],))

    places = cursor.fetchall()
    conn.close()

    return render_template('my_places.html', places=places, user=session.get('user'))


@app.route('/edit_place/<int:id>', methods=['GET', 'POST'])
def edit_place(id):
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM attractions WHERE id = ?', (id,))
    place = cursor.fetchone()

    if not place:
        flash('Место не найдено!')
        return redirect(url_for('my_places'))

    if place[7] != session['user']['id']:  # user_id
        flash('Вы не можете редактировать это место!')
        return redirect(url_for('my_places'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        detailed_description = request.form.get('detailed_description', '').strip()
        category = request.form.get('category', '').strip()
        address = request.form.get('address', '').strip()

        if not all([name, description, detailed_description, category, address]):
            flash('Все поля обязательны для заполнения!')
            return render_template('edit_place.html', place=place, user=session.get('user'))

        # Обновление с новым изображением
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    unique_filename = f"{timestamp}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    file.save(file_path)
                    new_image = f"uploads/{unique_filename}"

                    cursor.execute('''
                        UPDATE attractions 
                        SET name = ?, description = ?, detailed_description = ?, 
                            category = ?, address = ?, image = ?, status = 'pending'
                        WHERE id = ?
                    ''', (name, description, detailed_description, category, address, new_image, id))
                else:
                    flash('Недопустимый формат файла. Используйте PNG, JPG или JPEG.')
                    return render_template('edit_place.html', place=place, user=session.get('user'))
            else:
                # Без нового изображения
                cursor.execute('''
                    UPDATE attractions 
                    SET name = ?, description = ?, detailed_description = ?, 
                        category = ?, address = ?, status = 'pending'
                    WHERE id = ?
                ''', (name, description, detailed_description, category, address, id))
        else:
            # Без нового изображения
            cursor.execute('''
                UPDATE attractions 
                SET name = ?, description = ?, detailed_description = ?, 
                    category = ?, address = ?, status = 'pending'
                WHERE id = ?
            ''', (name, description, detailed_description, category, address, id))

        conn.commit()
        flash('Место успешно обновлено и отправлено на повторную модерацию!')
        conn.close()
        return redirect(url_for('my_places'))

    conn.close()
    return render_template('edit_place.html', place=place, user=session.get('user'))


@app.route('/delete_place/<int:id>')
def delete_place(id):
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()

    cursor.execute('SELECT user_id FROM attractions WHERE id = ?', (id,))
    place = cursor.fetchone()

    if place and place[0] == session['user']['id']:
        cursor.execute('DELETE FROM attractions WHERE id = ?', (id,))
        cursor.execute('DELETE FROM comments WHERE attraction_id = ?', (id,))
        cursor.execute('DELETE FROM likes WHERE attraction_id = ?', (id,))
        conn.commit()
        flash('Место успешно удалено!')
    else:
        flash('Вы не можете удалить это место!')

    conn.close()
    return redirect(url_for('my_places'))


@app.route('/attractions')
def attractions():
    category = request.args.get('category')
    page = request.args.get('page', 1, type=int)
    per_page = 9

    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()

    query = '''
        SELECT a.*, u.username 
        FROM attractions a 
        LEFT JOIN users u ON a.user_id = u.id 
        WHERE a.status = 'approved'
    '''
    count_query = 'SELECT COUNT(*) FROM attractions WHERE status = "approved"'
    params = []

    if category:
        query += ' AND a.category = ?'
        count_query += ' AND category = ?'
        params.append(category)

    # Получаем общее количество
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]

    # Получаем данные с пагинацией
    query += ' ORDER BY a.created_at DESC LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])

    cursor.execute(query, params)
    attractions_list = cursor.fetchall()

    # Получаем список категорий
    cursor.execute('SELECT DISTINCT category FROM attractions WHERE status = "approved" ORDER BY category')
    categories = [row[0] for row in cursor.fetchall()]

    conn.close()

    total_pages = (total + per_page - 1) // per_page

    return render_template('attractions.html',
                           attractions=attractions_list,
                           categories=categories,
                           user=session.get('user'),
                           current_category=category,
                           page=page,
                           total_pages=total_pages)


@app.route('/attraction/<int:id>')
def attraction(id):
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()

    # Увеличиваем счетчик просмотров
    cursor.execute('UPDATE attractions SET views = views + 1 WHERE id = ?', (id,))

    cursor.execute('''
        SELECT a.*, u.username 
        FROM attractions a 
        LEFT JOIN users u ON a.user_id = u.id 
        WHERE a.id = ?
    ''', (id,))

    attraction_data = cursor.fetchone()

    if not attraction_data:
        flash('Место не найдено!')
        return redirect(url_for('attractions'))

    # Получаем комментарии
    cursor.execute('''
        SELECT c.*, u.username 
        FROM comments c 
        LEFT JOIN users u ON c.user_id = u.id 
        WHERE c.attraction_id = ?
        ORDER BY c.created_at DESC
    ''', (id,))

    comments = cursor.fetchall()

    # Проверяем лайк пользователя
    user_liked = False
    if 'user' in session:
        cursor.execute('SELECT id FROM likes WHERE attraction_id = ? AND user_id = ?',
                       (id, session['user']['id']))
        user_liked = cursor.fetchone() is not None

    # Количество лайков
    cursor.execute('SELECT COUNT(*) FROM likes WHERE attraction_id = ?', (id,))
    likes_count = cursor.fetchone()[0]

    # Похожие места
    cursor.execute('''
        SELECT a.*, u.username 
        FROM attractions a 
        LEFT JOIN users u ON a.user_id = u.id 
        WHERE a.category = ? AND a.id != ? AND a.status = 'approved'
        ORDER BY RANDOM() 
        LIMIT 3
    ''', (attraction_data[4], id))

    similar = cursor.fetchall()

    conn.commit()
    conn.close()

    return render_template('attraction.html',
                           attraction=attraction_data,
                           comments=comments,
                           user_liked=user_liked,
                           likes_count=likes_count,
                           similar=similar,
                           user=session.get('user'))


@app.route('/like/<int:attraction_id>')
def like_attraction(attraction_id):
    if 'user' not in session:
        flash('Для оценки необходимо войти в систему!')
        return redirect(url_for('login'))

    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO likes (attraction_id, user_id)
            VALUES (?, ?)
        ''', (attraction_id, session['user']['id']))
        flash('Вы оценили это место!')
    except sqlite3.IntegrityError:
        cursor.execute('''
            DELETE FROM likes 
            WHERE attraction_id = ? AND user_id = ?
        ''', (attraction_id, session['user']['id']))
        flash('Вы убрали оценку!')

    conn.commit()
    conn.close()
    return redirect(url_for('attraction', id=attraction_id))


@app.route('/comment/<int:attraction_id>', methods=['POST'])
def add_comment(attraction_id):
    if 'user' not in session:
        flash('Для комментирования необходимо войти в систему!')
        return redirect(url_for('login'))

    content = request.form.get('content', '').strip()
    rating = request.form.get('rating', type=int)

    if not content:
        flash('Комментарий не может быть пустым!')
        return redirect(url_for('attraction', id=attraction_id))

    if rating and (rating < 1 or rating > 5):
        flash('Рейтинг должен быть от 1 до 5!')
        return redirect(url_for('attraction', id=attraction_id))

    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO comments (attraction_id, user_id, content, rating)
        VALUES (?, ?, ?, ?)
    ''', (attraction_id, session['user']['id'], content, rating))

    # Обновляем рейтинг места
    if rating:
        cursor.execute('''
            UPDATE attractions 
            SET rating = (
                SELECT AVG(rating) 
                FROM comments 
                WHERE attraction_id = ? AND rating IS NOT NULL
            ),
            votes = (
                SELECT COUNT(*) 
                FROM comments 
                WHERE attraction_id = ? AND rating IS NOT NULL
            )
            WHERE id = ?
        ''', (attraction_id, attraction_id, attraction_id))

    conn.commit()
    conn.close()

    flash('Комментарий успешно добавлен!')
    return redirect(url_for('attraction', id=attraction_id))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        email = request.form.get('email', '').strip()

        if not username or not password:
            flash('Имя пользователя и пароль обязательны!')
            return render_template('register.html')

        if len(username) < 3:
            flash('Имя пользователя должно быть не менее 3 символов!')
            return render_template('register.html')

        if len(password) < 6:
            flash('Пароль должен быть не менее 6 символов!')
            return render_template('register.html')

        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()

        try:
            cursor.execute('INSERT INTO users (username, password, email) VALUES (?, ?, ?)',
                           (username, password, email))
            conn.commit()
            flash('Регистрация успешна! Теперь войдите в систему.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Пользователь с таким именем уже существует!')
        except Exception as e:
            flash(f'Ошибка регистрации: {str(e)}')
        finally:
            conn.close()

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash('Заполните все поля!')
            return render_template('login.html')

        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()

        cursor.execute('SELECT id, username, is_admin FROM users WHERE username = ? AND password = ?',
                       (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user'] = {
                'id': user[0],
                'username': user[1],
                'is_admin': bool(user[2])
            }
            flash('Вход выполнен успешно!')
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль!')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Вы вышли из системы!')
    return redirect(url_for('login'))


# Админ-панель
@app.route('/admin')
def admin_panel():
    if 'user' not in session or not session['user'].get('is_admin'):
        flash('Доступ запрещен!')
        return redirect(url_for('index'))

    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()

    # Места на модерации
    cursor.execute('''
        SELECT a.*, u.username 
        FROM attractions a 
        LEFT JOIN users u ON a.user_id = u.id 
        WHERE a.status = 'pending'
        ORDER BY a.created_at DESC
    ''')
    pending = cursor.fetchall()

    # Статистика
    cursor.execute('SELECT COUNT(*) FROM attractions WHERE status = "pending"')
    pending_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM attractions WHERE status = "approved"')
    approved_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM users')
    users_count = cursor.fetchone()[0]

    conn.close()

    return render_template('admin.html',
                           pending=pending,
                           pending_count=pending_count,
                           approved_count=approved_count,
                           users_count=users_count,
                           user=session.get('user'))


@app.route('/admin/approve/<int:id>')
def approve_attraction(id):
    if 'user' not in session or not session['user'].get('is_admin'):
        flash('Доступ запрещен!')
        return redirect(url_for('index'))

    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()

    cursor.execute('UPDATE attractions SET status = "approved" WHERE id = ?', (id,))
    conn.commit()
    conn.close()

    flash('Место одобрено и опубликовано!')
    return redirect(url_for('admin_panel'))


@app.route('/admin/reject/<int:id>')
def reject_attraction(id):
    if 'user' not in session or not session['user'].get('is_admin'):
        flash('Доступ запрещен!')
        return redirect(url_for('index'))

    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()

    cursor.execute('UPDATE attractions SET status = "rejected" WHERE id = ?', (id,))
    conn.commit()
    conn.close()

    flash('Место отклонено!')
    return redirect(url_for('admin_panel'))


@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return redirect(url_for('attractions'))

    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()

    cursor.execute('''
        SELECT a.*, u.username 
        FROM attractions a 
        LEFT JOIN users u ON a.user_id = u.id 
        WHERE a.status = 'approved' 
        AND (a.name LIKE ? OR a.description LIKE ? OR a.address LIKE ?)
        ORDER BY a.created_at DESC
    ''', (f'%{query}%', f'%{query}%', f'%{query}%'))

    results = cursor.fetchall()
    conn.close()

    return render_template('search.html',
                           results=results,
                           query=query,
                           user=session.get('user'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=4000)