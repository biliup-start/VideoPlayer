import os
import hashlib


class DouyinDanmakuUtils:
    @staticmethod
    def load_webmssdk(js_file: str):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        js_path = os.path.join(dir_path, js_file)
        with open(js_path, 'r', encoding='utf-8') as f:
            return f.read()

    @staticmethod
    def get_user_unique_id() -> str:
        import random
        return str(random.randint(7300000000000000000, 7999999999999999999))

    @staticmethod
    def get_x_ms_stub(params: dict) -> str:
        sig_params = ','.join([f'{k}={v}' for k, v in params.items()])
        return hashlib.md5(sig_params.encode()).hexdigest()

    @staticmethod
    def get_signature(x_ms_stub: str):
        from DMR.LiveAPI.douyin import douyin_utils
        import jsengine
        ctx = jsengine.jsengine()
        user_agent = douyin_utils.get_headers()['user-agent']
        js_dom = f"""
document = {{}}
window = {{}}
navigator = {{
'userAgent': '{user_agent}'
}}
""".strip()
        js_enc = DouyinDanmakuUtils.load_webmssdk('webmssdk.js')
        final_js = js_dom + js_enc
        ctx.eval(final_js)
        function_caller = f"get_sign('{x_ms_stub}')"
        signature = ctx.eval(function_caller)
        # print("signature: ", signature)
        return signature
