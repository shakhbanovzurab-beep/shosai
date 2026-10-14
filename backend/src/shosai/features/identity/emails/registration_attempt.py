"""A warning to an existing account: someone tried to register its address (ADR 0045).

Registration answers the same whether the address is free or taken, so the form never
tells a stranger that an account exists; the owner learns of the attempt by this mail
instead and can sign in or reset the password from the sign-in page.
"""

from typing import Final

from shosai.core.email.templates import EmailTemplate

REGISTRATION_ATTEMPT_KEY: Final = "identity.registration_attempt"

BODY: Final = """
{{ e.heading(t.heading) }}
{% call e.paragraph() %}{{ t.lead }}{% endcall %}
{{ e.button(base_url ~ "/app/login", t.button) }}
{% call e.note() %}{{ t.note }}{% endcall %}
"""

_TEXTS: Final = {
    "en": {
        "subject": "Someone tried to sign up with your email",
        "preheader": "You already have a Shosai account, so nothing was created.",
        "heading": "You already have an account",
        "lead": (
            "Someone just tried to create a Shosai account with this email address. You already "
            "have one, so nothing was created."
        ),
        "button": "Sign in to Shosai",
        "note": (
            "If it was you, sign in, or reset your password on the sign-in page. If not, you can "
            "ignore this email: your account is safe."
        ),
    },
    "zh": {
        "subject": "有人嘗試用您的電子郵件註冊",
        "preheader": "您已經擁有 Shosai 帳戶，因此沒有建立任何新帳戶。",
        "heading": "您已經有帳戶了",
        "lead": (
            "剛才有人嘗試用這個電子郵件地址建立 Shosai 帳戶。您已經有帳戶，因此沒有建立任何新帳戶。"
        ),
        "button": "登入 Shosai",
        "note": (
            "如果是您本人，請登入，或在登入頁面重設密碼。如果不是，可以忽略這封郵件：您的帳戶是安全"
            "的。"
        ),
    },
    "es": {
        "subject": "Alguien intentó registrarse con tu correo",
        "preheader": "Ya tienes una cuenta de Shosai, así que no se creó nada.",
        "heading": "Ya tienes una cuenta",
        "lead": (
            "Alguien acaba de intentar crear una cuenta de Shosai con esta dirección de correo. Ya "
            "tienes una, así que no se creó nada."
        ),
        "button": "Iniciar sesión en Shosai",
        "note": (
            "Si fuiste tú, inicia sesión o restablece tu contraseña en la página de inicio de "
            "sesión. Si no, puedes ignorar este correo: tu cuenta está a salvo."
        ),
    },
    "ru": {
        "subject": "Кто-то пытался зарегистрироваться с вашей почтой",
        "preheader": "У вас уже есть аккаунт Shosai, поэтому новый не создан.",
        "heading": "У вас уже есть аккаунт",
        "lead": (
            "Только что кто-то попытался создать аккаунт Shosai с этим адресом почты. У вас он уже "
            "есть, поэтому ничего не создано."
        ),
        "button": "Войти в Shosai",
        "note": (
            "Если это были вы, войдите или сбросьте пароль на странице входа. Если нет, просто "
            "проигнорируйте письмо: ваш аккаунт в безопасности."
        ),
    },
    "hi": {
        "subject": "किसी ने आपके ईमेल से साइन अप करने की कोशिश की",
        "preheader": "आपका Shosai खाता पहले से है, इसलिए कुछ नया नहीं बना।",
        "heading": "आपका खाता पहले से है",
        "lead": (
            "अभी किसी ने इस ईमेल पते से Shosai खाता बनाने की कोशिश की। आपका खाता पहले से है, इसलिए कुछ नहीं "
            "बना।"
        ),
        "button": "Shosai में साइन इन करें",
        "note": (
            "अगर यह आप थे, तो साइन इन करें या साइन-इन पेज पर अपना पासवर्ड रीसेट करें। अगर नहीं, तो इस ईमेल "
            "को अनदेखा करें: आपका खाता सुरक्षित है।"
        ),
    },
    "ar": {
        "subject": "حاول شخص ما التسجيل باستخدام بريدك الإلكتروني",
        "preheader": "لديك حساب في Shosai بالفعل، لذلك لم يُنشأ أي شيء.",
        "heading": "لديك حساب بالفعل",
        "lead": (
            "حاول شخص ما للتو إنشاء حساب في Shosai بهذا العنوان. لديك حساب بالفعل، لذلك لم يُنشأ أي "
            "شيء."
        ),
        "button": "تسجيل الدخول إلى Shosai",
        "note": (
            "إذا كنت أنت، فسجّل الدخول أو أعد تعيين كلمة المرور من صفحة تسجيل الدخول. وإن لم تكن "
            "أنت، فتجاهل هذه الرسالة: حسابك آمن."
        ),
    },
    "pt": {
        "subject": "Alguém tentou se cadastrar com seu e-mail",
        "preheader": "Você já tem uma conta no Shosai, então nada foi criado.",
        "heading": "Você já tem uma conta",
        "lead": (
            "Alguém acabou de tentar criar uma conta no Shosai com este endereço de e-mail. Você "
            "já tem uma, então nada foi criado."
        ),
        "button": "Entrar no Shosai",
        "note": (
            "Se foi você, entre ou redefina sua senha na página de login. Se não foi, ignore este "
            "e-mail: sua conta está segura."
        ),
    },
    "fr": {
        "subject": "Quelqu’un a essayé de s’inscrire avec votre e-mail",
        "preheader": "Vous avez déjà un compte Shosai, rien n’a donc été créé.",
        "heading": "Vous avez déjà un compte",
        "lead": (
            "Quelqu’un vient d’essayer de créer un compte Shosai avec cette adresse e-mail. Vous "
            "en avez déjà un, rien n’a donc été créé."
        ),
        "button": "Se connecter à Shosai",
        "note": (
            "Si c’était vous, connectez-vous ou réinitialisez votre mot de passe depuis la page de "
            "connexion. Sinon, ignorez cet e-mail : votre compte est en sécurité."
        ),
    },
    "it": {
        "subject": "Qualcuno ha provato a registrarsi con la tua email",
        "preheader": "Hai già un account Shosai, quindi non è stato creato nulla.",
        "heading": "Hai già un account",
        "lead": (
            "Qualcuno ha appena provato a creare un account Shosai con questo indirizzo email. Ne "
            "hai già uno, quindi non è stato creato nulla."
        ),
        "button": "Accedi a Shosai",
        "note": (
            "Se sei stato tu, accedi o reimposta la password dalla pagina di accesso. Altrimenti "
            "ignora questa email: il tuo account è al sicuro."
        ),
    },
    "de": {
        "subject": "Jemand wollte sich mit deiner E-Mail-Adresse registrieren",
        "preheader": "Du hast bereits ein Shosai-Konto, daher wurde nichts angelegt.",
        "heading": "Du hast bereits ein Konto",
        "lead": (
            "Gerade hat jemand versucht, mit dieser E-Mail-Adresse ein Shosai-Konto anzulegen. Du "
            "hast schon eines, daher wurde nichts angelegt."
        ),
        "button": "Bei Shosai anmelden",
        "note": (
            "Warst du das, melde dich an oder setze dein Passwort auf der Anmeldeseite zurück. "
            "Wenn nicht, ignoriere diese E-Mail: Dein Konto ist sicher."
        ),
    },
    "ja": {
        "subject": "あなたのメールアドレスで登録しようとした人がいます",
        "preheader": (
            "すでに Shosai のアカウントをお持ちのため、新しいアカウントは作成されていません。"
        ),
        "heading": "すでにアカウントをお持ちです",
        "lead": (
            "先ほど、このメールアドレスで Shosai "
            "のアカウントを作成しようとした人がいます。すでにアカウントをお持ちのため、何も作成されていません。"
        ),
        "button": "Shosai にサインイン",
        "note": (
            "ご自身の操作であれば、サインインするか、サインインページでパスワードをリセットしてくだ"
            "さい。心当たりがなければ、このメールは無視してください。アカウントは安全です。"
        ),
    },
    "ko": {
        "subject": "누군가 회원님의 이메일로 가입하려고 했습니다",
        "preheader": "이미 Shosai 계정이 있어 새 계정은 만들어지지 않았습니다.",
        "heading": "이미 계정이 있습니다",
        "lead": (
            "방금 누군가 이 이메일 주소로 Shosai 계정을 만들려고 했습니다. 이미 계정이 있어 "
            "아무것도 만들어지지 않았습니다."
        ),
        "button": "Shosai에 로그인",
        "note": (
            "본인이었다면 로그인하거나 로그인 페이지에서 비밀번호를 재설정하세요. 본인이 아니라면 "
            "이 이메일을 무시하세요. 계정은 안전합니다."
        ),
    },
    "id": {
        "subject": "Seseorang mencoba mendaftar dengan email Anda",
        "preheader": "Anda sudah punya akun Shosai, jadi tidak ada yang dibuat.",
        "heading": "Anda sudah punya akun",
        "lead": (
            "Seseorang baru saja mencoba membuat akun Shosai dengan alamat email ini. Anda sudah "
            "punya akun, jadi tidak ada yang dibuat."
        ),
        "button": "Masuk ke Shosai",
        "note": (
            "Jika itu Anda, masuklah atau atur ulang kata sandi di halaman masuk. Jika bukan, "
            "abaikan email ini: akun Anda aman."
        ),
    },
    "tr": {
        "subject": "Biri e-postanızla kaydolmaya çalıştı",
        "preheader": "Zaten bir Shosai hesabınız var, bu yüzden hiçbir şey oluşturulmadı.",
        "heading": "Zaten bir hesabınız var",
        "lead": (
            "Az önce biri bu e-posta adresiyle bir Shosai hesabı oluşturmaya çalıştı. Zaten bir "
            "hesabınız olduğu için hiçbir şey oluşturulmadı."
        ),
        "button": "Shosai’de oturum açın",
        "note": (
            "Bu sizseniz oturum açın veya giriş sayfasında şifrenizi sıfırlayın. Değilse bu "
            "e-postayı yok sayabilirsiniz: hesabınız güvende."
        ),
    },
    "vi": {
        "subject": "Có người đã thử đăng ký bằng email của bạn",
        "preheader": "Bạn đã có tài khoản Shosai nên không có gì được tạo.",
        "heading": "Bạn đã có tài khoản",
        "lead": (
            "Vừa có người thử tạo tài khoản Shosai bằng địa chỉ email này. Bạn đã có tài khoản nên "
            "không có gì được tạo."
        ),
        "button": "Đăng nhập Shosai",
        "note": (
            "Nếu đó là bạn, hãy đăng nhập hoặc đặt lại mật khẩu trên trang đăng nhập. Nếu không, "
            "bạn có thể bỏ qua email này: tài khoản của bạn vẫn an toàn."
        ),
    },
    "th": {
        "subject": "มีคนพยายามสมัครด้วยอีเมลของคุณ",
        "preheader": "คุณมีบัญชี Shosai อยู่แล้ว จึงไม่มีการสร้างบัญชีใหม่",
        "heading": "คุณมีบัญชีอยู่แล้ว",
        "lead": "เมื่อสักครู่มีคนพยายามสร้างบัญชี Shosai ด้วยอีเมลนี้ คุณมีบัญชีอยู่แล้ว จึงไม่มีการสร้างสิ่งใด",
        "button": "เข้าสู่ระบบ Shosai",
        "note": (
            "หากเป็นคุณ โปรดเข้าสู่ระบบหรือรีเซ็ตรหัสผ่านในหน้าเข้าสู่ระบบ หากไม่ใช่ คุณสามารถเพิกเฉยต่ออีเมลนี้ได้ "
            "บัญชีของคุณปลอดภัย"
        ),
    },
}

REGISTRATION_ATTEMPT: Final = EmailTemplate(key=REGISTRATION_ATTEMPT_KEY, body=BODY, texts=_TEXTS)
