#!/usr/bin/env python3

import postgresql
import flask
import json
import re

from wtforms import Form, BooleanField, StringField, PasswordField, validators
from wtforms.widgets import TextArea

app = flask.Flask(__name__)

# disables JSON pretty-printing in flask.jsonify
# app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

link_regexp = '''(?i)(https?://[^\s\"]+)'''

def encode_description(desc):
    temp = desc.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br />") 
    temp = re.sub(link_regexp, '''<a href="\\1">\\1</a>''', temp)
    return temp

app.jinja_env.globals.update(encode_description = encode_description)

class SubmitForm(Form):
    description = StringField('Description', widget=TextArea())

class ClearDiscussedForm(Form):
    sure = BooleanField('Sure')

def db_conn():
    return postgresql.open('pq://eax@localhost/eax')

@app.route('/')
def root():
    return flask.redirect('/themes')

def report_error(code):
    data = flask.render_template('error.html', message = 'Error code {}'.format(code))
    return (data, code)

@app.errorhandler(400)
def error_400(e):
    return report_error(400)

@app.errorhandler(404)
def error_404(e):
    return report_error(404)

@app.errorhandler(405)
def error_405(e):
    return report_error(405)

@app.route('/static/<path:path>', methods=['GET'])
def get_static(path):
    return send_from_directory('static', path)

@app.route('/recording', methods=['GET'])
def get_recording():
    with db_conn() as db:
        #select = "SELECT t.*, u.login FROM themes AS t LEFT JOIN users AS u ON u.id = t.created_by" 
        #current = db.query(select + " WHERE t.status = 'c'")
        #regular = db.query(select + " WHERE t.status = 'r' ORDER BY t.priority DESC")
        #discussed = db.query(select + " WHERE t.status = 'd' ORDER BY t.updated")
        return flask.render_template('recording.html', section = "recording")

@app.route('/themes', methods=['GET'])
def get_themes():
    with db_conn() as db:
        select = "SELECT t.*, u.login FROM themes AS t LEFT JOIN users AS u ON u.id = t.created_by" 
        current = db.query(select + " WHERE t.status = 'c'")
        regular = db.query(select + " WHERE t.status = 'r' ORDER BY t.priority DESC")
        discussed = db.query(select + " WHERE t.status = 'd' ORDER BY t.updated")
        return flask.render_template('themes.html', section = "themes", current = current, regular = regular, discussed = discussed)

@app.route('/submit', methods=['GET', 'POST'])
def get_submit():
    form = SubmitForm(flask.request.form)
    if flask.request.method == 'POST' and form.validate():
         with db_conn() as db:
            [(uid,)] = db.query("""SELECT id FROM users WHERE login = 'admin'""")
            # app.logger.info("""uid = {}, description = {}""".format(uid, form.description.data))
            insert = db.prepare(
                "INSERT INTO themes (title, url, description, rev, created, created_by, updated, updated_by, current_at, discussed_at, status, priority) " +
                "VALUES ('', '', $1, 1, now(), $2, now(), $2, now(), now(), 'r', 30) ")
            insert(form.description.data, uid)
            return flask.redirect('/themes')

    return flask.render_template('submit.html', section = "submit", form = form)

@app.route('/themes/<int:theme_id>/edit', methods=['GET', 'POST'])
def get_themes_edit(theme_id):
    form = SubmitForm(flask.request.form)
    if flask.request.method == 'POST' and form.validate():
         with db_conn() as db:
            update = db.prepare("""UPDATE themes SET description = $2, updated = now(), rev = rev + 1 WHERE id = $1""")
            update(theme_id, form.description.data)
            return flask.redirect('/themes')
    else:
        with db_conn() as db:
            select = db.prepare("""SELECT description FROM themes WHERE id = $1""")
            [(description,)] = select(theme_id)
            form = SubmitForm(description = description)
            return flask.render_template('edit.html', section = "submit", theme_id = theme_id, form = form)


@app.route('/themes/<int:theme_id>/mark/current', methods=['GET'])
def get_mark_current(theme_id):
    with db_conn() as db:
        update = db.prepare("""UPDATE themes SET status = 'c', updated = now(), current_at = now() WHERE id = $1""")
        update(theme_id)
        return flask.redirect('/themes')

@app.route('/themes/<int:theme_id>/mark/regular', methods=['GET'])
def get_mark_regular(theme_id):
    with db_conn() as db:
        update = db.prepare("""UPDATE themes SET status = 'r', updated = now() WHERE id = $1""")
        update(theme_id)
        return flask.redirect('/themes')

@app.route('/themes/<int:theme_id>/mark/discussed', methods=['GET'])
def get_mark_discussed(theme_id):
    with db_conn() as db:
        update = db.prepare("""UPDATE themes SET status = 'd', updated = now(), discussed_at = now() WHERE id = $1""")
        update(theme_id)
        return flask.redirect('/themes')

@app.route('/themes/<int:theme_id>/priority/<string:action>', methods=['GET'])
def get_priority(theme_id, action):
    if not (action == "up" or action == "down"):
        return flask.redirect('/themes')

    delta = 10
    if action == "down":
        delta = -delta

    with db_conn() as db:
        update = db.prepare("""UPDATE themes SET priority = least(50, greatest(10, priority + ($2))), updated = now() WHERE id = $1""")
        update(theme_id, delta)
        return flask.redirect('/themes')

@app.route('/themes/discussed/export', methods=['GET', 'POST'])
def post_discussed_export():
    with db_conn() as db:
        desc_list = db.query("""SELECT description FROM themes WHERE status = 'd' ORDER BY updated""")
        urls = []
        for (desc,) in desc_list:
            # app.logger.info("""description = {}""".format(desc))
            for m in re.finditer(link_regexp, desc):
                urls.append(m.group(1))
        return flask.render_template('export.html', section = "themes", urls = urls)


@app.route('/themes/discussed/clear', methods=['POST'])
def post_discussed_clear():
    form = ClearDiscussedForm(flask.request.form)
    if form.validate() and form.sure.data == True:
         with db_conn() as db:
            db.query("""DELETE FROM themes WHERE status = 'd'""")
    return flask.redirect('/themes')

if __name__ == '__main__':
    app.debug = True  # enables auto reload during development
    app.run()
