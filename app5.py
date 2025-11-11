from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'secret_key_123'
app.config['DATABASE'] = 'izhevsk.db'


def init_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attractions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            address TEXT,
            image TEXT
        )
    ''')

    attractions_data = [
        ('Михайловский собор', 'Главный храм Ижевска с красивой архитектурой', 'Архитектура', 'ул. К. Маркса, 222',
         'sobor.jpg'),
        ('Набережная пруда', 'Живописная набережная для прогулок', 'Прогулки', 'Набережная пруда', 'naberezhnaya.jpg'),
        ('Музей Ижмаш', 'История оружейного завода и города', 'Музеи', 'ул. Свердлова, 32', 'izhmash.jpg'),
        ('Парк Космонавтов', 'Парк с аллеей славы космонавтов', 'Парки', 'ул. 9 Января, 213', 'park.jpg'),
        ('Зоопарк', 'Крупный зоопарк с разнообразными животными', 'Развлечения', 'ул. Кирова, 8', 'zoo.jpg'),
        ('Арсенал', 'Культурный центр с выставками', 'Культура', 'ул. Коммунаров, 287', 'arsenal.jpg'),
        ('Памятник Ижику', 'Символ Ижевска - крокодил Ижик', 'Памятники', 'ул. Советская, 1', 'izhik.jpg'),
        ('Цирк', 'Стационарный цирк с представлениями', 'Развлечения', 'ул. Красноармейская, 136', 'circus.jpg'),
        ('Свято-Троицкий собор', 'Старейший храм Ижевска', 'Архитектура', 'ул. Удмуртская, 220', 'troitsky.jpg'),
        ('Летний сад', 'Старейший парк города', 'Парки', 'ул. Милиционная, 4', 'letniy_sad.jpg'),
        ('Памятник крокодилу', 'Необычный памятник в центре города', 'Памятники', 'ул. Советская, 22', 'crocodile.jpg'),
        ('Национальный музей', 'Музей истории Удмуртской республики', 'Музеи', 'ул. Коммунаров, 287', 'museum.jpg'),
        ('Театр оперы и балета', 'Государственный театр Удмуртии', 'Культура', 'ул. Пушкинская, 221', 'teatr.jpg'),
        ('Сквер у Вечного огня', 'Мемориальный комплекс', 'Памятники', 'Центральная площадь', 'skver.jpg')
    ]

    cursor.execute('SELECT COUNT(*) FROM attractions')
    count = cursor.fetchone()[0]

    if count == 0:
        cursor.executemany('INSERT INTO attractions (name, description, category, address, image) VALUES (?,?,?,?,?)',
                           attractions_data)

    conn.commit()
    conn.close()


@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM attractions LIMIT 6')
    attractions = cursor.fetchall()
    conn.close()
    return render_template('index.html', attractions=attractions, user=session.get('user'))


@app.route('/attractions')
def attractions():
    if 'user' not in session:
        return redirect(url_for('login'))

    category = request.args.get('category')

    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()

    if category:
        cursor.execute('SELECT * FROM attractions WHERE category = ?', (category,))
    else:
        cursor.execute('SELECT * FROM attractions')

    attractions = cursor.fetchall()
    conn.close()

    return render_template('attractions.html', attractions=attractions, user=session.get('user'),
                           current_category=category)


@app.route('/attraction/<int:id>')
def attraction(id):
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM attractions WHERE id = ?', (id,))
    attraction = cursor.fetchone()
    conn.close()
    if not attraction:
        flash('Достопримечательность не найдена!')
        return redirect(url_for('attractions'))

    return render_template('attraction.html', attraction=attraction, user=session.get('user'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            flash('Заполните все поля!')
            return render_template('register.html')

        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            conn.commit()
            flash('Регистрация успешна! Теперь войдите в систему.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Пользователь с таким именем уже существует!')
        except Exception as e:
            flash('Ошибка регистрации!')
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            flash('Заполните все поля!')
            return render_template('login.html')

        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user'] = {'username': username, 'id': user[0]}
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

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=4000)
