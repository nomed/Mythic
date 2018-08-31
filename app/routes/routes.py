from app import apfell, db_objects, links, use_ssl
from sanic.response import json
from sanic import response
from sanic.exceptions import NotFound, abort
from jinja2 import Environment, PackageLoader
from app.database_models.model import Operator
from app.forms.loginform import LoginForm, RegistrationForm
import datetime
import app.crypto as crypto
from sanic_jwt import BaseEndpoint, utils, exceptions
from sanic_jwt.decorators import protected, inject_user
import json as js

env = Environment(loader=PackageLoader('app', 'templates'))


@apfell.route("/")
@inject_user()
@protected()
async def index(request, user):
    template = env.get_template('main_page.html')
    content = template.render(name=user['username'], links=links)
    return response.html(content)


class Login(BaseEndpoint):
    async def get(self, request):
        form = LoginForm(request)
        errors = {}
        errors['username_errors'] = '<br>'.join(form.username.errors)
        errors['password_errors'] = '<br>'.join(form.password.errors)
        template = env.get_template('login.html')
        content = template.render(links=links, form=form, errors=errors)
        return response.html(content)

    async def post(self, request):
        form = LoginForm(request)
        errors = {}
        if form.validate():
            username = form.username.data
            password = form.password.data
            try:
                user = await db_objects.get(Operator, username=username)
                if await user.check_password(password):
                    try:
                        user.last_login = datetime.datetime.now()
                        await db_objects.update(user)  # update the last login time to be now
                        access_token, output = await self.responses.get_access_token_output(
                            request,
                            {'user_id': user.id},
                            self.config,
                            self.instance)
                        refresh_token = await self.instance.auth.generate_refresh_token(request, {'user_id': user.id})
                        output.update({
                            self.config.refresh_token_name(): refresh_token
                        })
                        resp = response.redirect("/")
                        resp.cookies[self.config.cookie_access_token_name()] = access_token
                        resp.cookies[self.config.cookie_access_token_name()]['httponly'] = True
                        resp.cookies[self.config.cookie_refresh_token_name()] = refresh_token
                        resp.cookies[self.config.cookie_refresh_token_name()]['httponly'] = True
                        return resp
                    except Exception as e:
                        print(e)
                        errors['validate_errors'] = "failed to update login time"
            except Exception as e:
                print(e)
            errors['validate_errors'] = "Username or password invalid"
        errors['username_errors'] = '<br>'.join(form.username.errors)
        errors['password_errors'] = '<br>'.join(form.password.errors)
        template = env.get_template('login.html')
        content = template.render(links=links, form=form, errors=errors)
        return response.html(content)


class Register(BaseEndpoint):
    async def get(self, request, *args, **kwargs):
        errors = {}
        form = RegistrationForm(request)
        template = env.get_template('register.html')
        content = template.render(links=links, form=form, errors=errors)
        return response.html(content)

    async def post(self, request, *args, **kwargs):
        errors = {}
        form = RegistrationForm(request)
        if form.validate():
            username = form.username.data
            password = await crypto.hash_SHA512(form.password.data)
            # we need to create a new user
            try:
                user = await db_objects.create(Operator, username=username, password=password)
                user.last_login = datetime.datetime.now()
                await db_objects.update(user)  # update the last login time to be now
                # generate JWT token to be stored in a cookie
                access_token, output = await self.responses.get_access_token_output(
                    request,
                    {'user_id': user.id},
                    self.config,
                    self.instance)
                refresh_token = await self.instance.auth.generate_refresh_token(request, {'user_id': user.id})
                output.update({
                    self.config.refresh_token_name(): refresh_token
                })
                resp = response.redirect("/")
                resp.cookies[self.config.cookie_access_token_name()] = access_token
                resp.cookies[self.config.cookie_access_token_name()]['httponly'] = True
                resp.cookies[self.config.cookie_refresh_token_name()] = refresh_token
                resp.cookies[self.config.cookie_refresh_token_name()]['httponly'] = True
                return resp
            except:
                # failed to insert into database
                errors['validate_errors'] = "failed to create user"
        errors['token_errors'] = '<br>'.join(form.csrf_token.errors)
        errors['username_errors'] = '<br>'.join(form.username.errors)
        errors['password_errors'] = '<br>'.join(form.password.errors)
        template = env.get_template('register.html')
        content = template.render(links=links, form=form, errors=errors)
        return response.html(content)


class UIRefresh(BaseEndpoint):
    async def get(self, request, *args, **kwargs):
        # go here if we're in the browser and our JWT expires so we can update it and continue on
        payload = self.instance.auth.extract_payload(request, verify=False)
        try:
            user = await utils.call(
                self.instance.auth.retrieve_user, request, payload=payload
            )
        except exceptions.MeEndpointNotSetup:
            raise exceptions.RefreshTokenNotImplemented

        user_id = await self.instance.auth._get_user_id(user)
        refresh_token = await utils.call(
            self.instance.auth.retrieve_refresh_token,
            request=request,
            user_id=user_id,
        )
        if isinstance(refresh_token, bytes):
            refresh_token = refresh_token.decode("utf-8")
        token = await self.instance.auth.retrieve_refresh_token_from_request(
            request
        )

        if refresh_token != token:
            raise exceptions.AuthenticationFailed()

        access_token, output = await self.responses.get_access_token_output(
            request, user, self.config, self.instance
        )
        redirect_to = request.headers['referer'] if 'referer' in request.headers else "/"
        resp = response.redirect(redirect_to)
        resp.cookies[self.config.cookie_access_token_name()] = access_token
        resp.cookies[self.config.cookie_access_token_name()]['httponly'] = True
        return resp


@apfell.route("/settings", methods=['GET'])
@inject_user()
@protected()
async def settings(request, user):
    template = env.get_template('settings.html')
    try:
        operator = Operator.get(Operator.username == user['username'])
        if use_ssl:
            content = template.render(links=links, name=user['username'], http="https", ws="wss", op=operator.to_json())
        else:
            content = template.render(links=links, name=user['username'], http="http", ws="ws", op=operator.to_json())
        return response.html(content)
    except Exception as e:
        print(e)
        return abort(404)


@apfell.route("/logout")
@protected()
async def logout(request):
    resp = response.redirect("/login")
    del resp.cookies['access_token']
    del resp.cookies['refresh_token']
    return resp


@apfell.exception(NotFound)
async def handler_404(request, exception):
    return json({'error': 'Not Found'})


@apfell.middleware('request')
async def reroute_to_login(request):
    # if a browser attempted to go somewhere without a cookie, reroute them to the login page
    if 'access_token' not in request.cookies and 'authorization' not in request.headers:
        if "/login" not in request.path and "/register" not in request.path and "/auth" not in request.path:
            if apfell.config['API_BASE'] not in request.path:
                return response.redirect("/login")


@apfell.middleware('response')
async def reroute_to_refresh(request, resp):
    # if you browse somewhere and get greeted with response.json.get('reasons')[0] and "Signature has expired"
    if resp and resp.status == 403 and resp.content_type == "application/json":
        output = js.loads(resp.body)
        if 'reasons' in output and 'Signature has expired' in output['reasons'][0]:
            # unauthorized due to signature expiring, not invalid auth, redirect to /refresh
            if request.cookies['refresh_token'] and request.cookies['access_token']:
                # auto generate a new
                return response.redirect("/uirefresh")


# add links to the routes in this file at the bottom
links['index'] = apfell.url_for('index')
links['login'] = links['WEB_BASE'] + "/login"
links['logout'] = apfell.url_for('logout')
links['register'] = links['WEB_BASE'] + "/register"
links['settings'] = apfell.url_for('settings')
