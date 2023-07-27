from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager,\
      login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
import os

CURRENT_YEAR_FOR_FOOTER = date.today().strftime("%Y")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("FLASK_SECRET_KEY")

# EXTENSIONS FLASK
Bootstrap(app)
ckeditor = CKEditor(app)
login_manager = LoginManager(app)
gravatar = Gravatar(app,
                    size=500,
                    rating='g',
                    default='retro',
                    force_default=False,
                    use_ssl=False,
                    base_url=None)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("POSTGRES_MY_URL")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.filter_by(id = user_id).first()


##CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), nullable=False)
    password = db.Column(db.String(250), nullable=False)

    posts = relationship('BlogPost', back_populates='author')
    comments = relationship('Comment', back_populates='comment_author')


    def __repr__(self) -> str:
        return f"<User: {self.name}>"
    

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    author = relationship('User', back_populates='posts')
    comments = relationship('Comment', back_populates='parent_post')

    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    def __repr__(self):
        return f"Post Title: {self.title} // author: {self.author.name}"


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    comment_author = relationship('User', back_populates='comments')
    parent_post = relationship('BlogPost', back_populates='comments')
    
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    def __repr__(self):
        return f"Comment Author: {self.comment_author.name}"


# CREATE ALL TABLES IN THE DATABASE
with app.app_context():
    db.create_all()  


def admin_only(func):
    @wraps(func)
    def inner_fuction(*args, **kwargs):
        if current_user.id != 1:
            return abort(code=403)
        
        return func(*args, **kwargs)

    return inner_fuction


@app.route('/')
def get_all_posts():
    """ Show all blog posts in home page """
    posts = BlogPost.query.all()

    return render_template("index.html", all_posts=posts, current_year=CURRENT_YEAR_FOR_FOOTER)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """ Responsible for registering new users """
    register_form = RegisterForm()
    if register_form.validate_on_submit():
        hash_and_salted_password = generate_password_hash(register_form.password.data, method='pbkdf2', salt_length=8)
        
        if User.query.filter_by(email = register_form.email.data).first():
            flash(message="You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))
            
        new_user = User(
            name = register_form.name.data,
            email = register_form.email.data,
            password = hash_and_salted_password,
        )

        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for('get_all_posts'))
    
    return render_template("register.html", form=register_form, current_year=CURRENT_YEAR_FOR_FOOTER)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """ Responsible for user login """
    login_form = LoginForm()
    if login_form.validate_on_submit():
        user = User.query.filter_by(email = login_form.email.data).first()
        if user:
            if check_password_hash(pwhash=user.password, password=login_form.password.data):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else: 
                flash(message="Password incorrect, please try again.")
        else:
            flash(message="That email does not exist, please try again.")
        
        return redirect(url_for('login'))
            
    return render_template("login.html", form=login_form, current_year=CURRENT_YEAR_FOR_FOOTER)


@app.route('/logout')
def logout():
    """ Responsible for user logout """
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    """ Responsible for showing all database publications """
    requested_post = BlogPost.query.filter_by(id = post_id).first()
    all_comments_of_post = Comment.query.all()
    form = CommentForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash(message="you need to log in to comment!")
            return redirect(url_for('login'))
    
        new_comment = Comment(
            text=form.comment_text.data,
            comment_author=current_user,
            parent_post=requested_post
            )
        
        db.session.add(new_comment)
        db.session.commit()

    return render_template("post.html", post=requested_post, form=form, all_comments=all_comments_of_post, current_year=CURRENT_YEAR_FOR_FOOTER)


@app.route("/new-post", methods=['GET', 'POST'])
@login_required
@admin_only
def add_new_post():
    """ Responsible for creating publications """
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y"),
        )
        db.session.add(new_post)
        db.session.commit()
        
        return redirect(url_for("get_all_posts"))
    
    return render_template("make-post.html", form=form, current_year=CURRENT_YEAR_FOR_FOOTER)


@app.route("/edit-post/<int:post_id>", methods=['GET', 'POST'])
@login_required
@admin_only
def edit_post(post_id):
    """ Responsible for database publication editing """
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()

        return redirect(url_for("show_post", post_id=post.id, current_year=CURRENT_YEAR_FOR_FOOTER))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@login_required
@admin_only
def delete_post(post_id):
    """ Responsible for deleting a publication from the database """
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()

    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html", current_year=CURRENT_YEAR_FOR_FOOTER)


@app.route("/contact", methods=['GET', 'POST'])
def contact():
    return render_template("contact.html", current_year=CURRENT_YEAR_FOR_FOOTER)


if __name__ == "__main__":
    app.run(debug=True)
