import streamlit as st
import time

# --- فحص المكتبات ---
try:
    from newspaper import Article
    import requests
    import base64
    import google.generativeai as genai
    from PIL import Image, ImageEnhance, ImageOps
    import io
    import re
    import numpy as np
except ImportError as e:
    st.error(f"❌ مكتبة ناقصة: {e}")
    st.stop()

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Editor Pro 13.0", layout="wide", page_icon="🛡️")

# --- 2. القائمة الجانبية ---
with st.sidebar:
    st.header("1. البيانات")
    api_key = st.text_input("مفتاح Gemini API", type="password")
    wp_url = st.text_input("رابط الموقع", "https://driouchcity.com")
    wp_user = st.text_input("اسم المستخدم")
    wp_password = st.text_input("كلمة مرور التطبيق", type="password")
    
    st.divider()
    st.header("2. المحتوى")
    langs = ["العربية", "الإسبانية", "الفرنسية", "الإنجليزية", "الهولندية", "الألمانية"]
    target_language = st.selectbox("اللغة:", langs)
    
    st.divider()
    st.header("3. الصورة")
    crop_logo = st.checkbox("قص اللوغو", value=True)
    logo_ratio = st.slider("نسبة القص", 0.0, 0.25, 0.12, step=0.01)
    apply_mirror = st.checkbox("قلب الصورة", value=True)
    red_factor = st.slider("لمسة الأحمر", 0.0, 0.3, 0.08, step=0.01)

# --- 3. الدوال ---

def clean_text(text):
    if not text: return ""
    junk = ["###SPLIT###", "###", "##", "**", "*", "العنوان:", "المتن:"]
    for j in junk:
        text = text.replace(j, "")
    return text.strip()

def resize_768(img):
    tw, th = 768, 432
    cw, ch = img.size
    tr, cr = tw / th, cw / ch
    
    if cr > tr:
        nh = th
        nw = int(nh * cr)
        img = img.resize((nw, nh), Image.LANCZOS)
        left = (nw - tw) // 2
        img = img.crop((left, 0, left + tw, th))
    else:
        nw = tw
        nh = int(nw / cr)
        img = img.resize((nw, nh), Image.LANCZOS)
        top = (nh - th) // 2
        img = img.crop((0, top, tw, top + th))
    return img

def process_img(src, is_url, crop, c_amt, mirror, red):
    try:
        if is_url:
            r = requests.get(src, stream=True, timeout=10)
            img = Image.open(r.raw)
        else:
            img = Image.open(src)
            
        if img.mode != 'RGB': 
            img = img.convert('RGB')
            
        if crop:
            w, h = img.size
            new_h = int(h * (1 - c_amt))
            img = img.crop((0, 0, w, new_h))
            
        if mirror: 
            img = ImageOps.mirror(img)
            
        img = resize_768(img)
        
        # الألوان السينمائية
        img = ImageEnhance.Color(img).enhance(1.6)
        img = ImageEnhance.Contrast(img).enhance(1.15)
        img = ImageEnhance.Sharpness(img).enhance(1.3)
        
        if red > 0:
            # هنا قمنا بتكسير السطر لتفادي الخطأ السابق
            color = (180, 20, 20)
            ov = Image.new('RGB', img.size, color)
            img = Image.blend(img, ov, alpha=red)
            
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=95)
        return buf.getvalue()
    except: return None

def ai_rewrite(txt, key, lang):
    try:
        genai.configure(api_key=key)
        mod = genai.GenerativeModel('gemini-2.0-flash')
        
        # البرومبت "رئيس التحرير" كما طلبت
        pmt = f"""
        **الدور:** رئيس تحرير مخضرم.
        **المهمة:** صياغة وترجمة للنص التالي إلى: {lang}.
        
        **القواعد الصارمة:**
        1. الفاصل الإجباري: ###SPLIT###
        2. الهيكلة: 4 فقرات على الأقل و 10 كحد أقصى.
        3. الفقرات: دسمة ومتوسطة الطول (5-7 أسطر).
        4. الأسلوب: بشري 100%، تجنب (مما لا شك فيه، الجدير بالذكر).
        
        **النص:** {txt[:12000]}
        """
        return mod.generate_content(pmt).text
    except Exception as e: return f"Error: {e}"

def wp_up_clean(ib, tit, con, url, usr, pwd):
    cred = f"{usr}:{pwd}"
    tok = base64.b64encode(cred.encode()).decode('utf-8')
    head = {'Authorization': f'Basic {tok}'}
    
    mid = 0
    if ib:
        h2 = head.copy()
        h2.update({
            'Content-Disposition': 'attachment; filename=news.jpg', 
            'Content-Type': 'image/jpeg'
        })
        try:
            api = f"{url}/wp-json/wp/v2/media"
            r = requests.post(api, headers=h2, data=ib)
            if r.status_code == 201: mid = r.json()['id']
        except: pass

    h3 = head.copy()
    h3['Content-Type'] = 'application/json'
    d = {
        'title': tit, 
        'content': con, 
        'status': 'draft', 
        'featured_media': mid
    }
    return requests.post(f"{url}/wp-json/wp/v2/posts", headers=h3, json=d)

def wp_up_img(ib, url, usr, pwd):
    cred = f"{usr}:{pwd}"
    tok = base64.b64encode(cred.encode()).decode('utf-8')
    head = {'Authorization': f'Basic {tok}'}
    
    h2 = head.copy()
    fn = f"img-{int(time.time())}.jpg"
    h2.update({
        'Content-Disposition': f'attachment; filename={fn}', 
        'Content-Type': 'image/jpeg'
    })
    
    api = f"{url}/wp-json/wp/v2/media"
    return requests.post(api, headers=h2, data=ib)

# --- 4. الواجهة ---
st.title("📰 المحرر (النسخة المصفحة 13.0)")
t1, t2, t3 = st.tabs(["🔗 رابط", "📝 يدوي", "🖼️ صورة"])
mode, l_val, f_val, t_val, i_only = None, "", None, "", None

with t1:
    l_val = st.text_input("رابط الخبر:")
    if st.button("🚀 معالجة (رابط)"): mode = "link"
with t2:
    f_val = st.file_uploader("الصورة", key="mi")
    t_val = st.text_area("النص", height=150)
    if st.button("🚀 معالجة (يدوي)"): mode = "manual"
with t3:
    ic = st.radio("المصدر:", ["ملف", "رابط"], horizontal=True)
    if ic == "ملف": i_only = st.file_uploader("الصورة", key="iof")
    else: i_only = st.text_input("الرابط:", key="iou")
    if st.button("🎨 رفع صورة فقط"): mode = "img_only"

if mode:
    if not api_key or not wp_password:
        st.error("⚠️ أدخل البيانات!")
    else:
        st.divider()
        stat = st.container()
        
        # --- معالجة صورة فقط ---
        if mode == "img_only":
            if not i_only: st.error("اختر صورة!")
            else:
                stat.info("جاري المعالجة...")
                iu = True if isinstance(i_only, str) else False
                fi = process_img(i_only, iu, crop_logo, logo_ratio, apply_mirror, red_factor)
                if fi:
                    st.image(fi, caption="النهاية", width=400)
                    r = wp_up_img(fi, wp_url, wp_user, wp_password)
                    if r.status_code == 201:
                        st.success("✅ تم الرفع!")
                        st.text_input("الرابط:", r.json()['source_url'])
                    else: st.error(r.text)
        
        # --- معالجة مقال ---
        else:
            stat.info("جاري العمل...")
            try:
                tt, ti, iu = "", None, False
                if mode == "link":
                    a = Article(l_val)
                    a.download()
                    a.parse()
                    tt, ti, iu = a.text, a.top_image, True
                else:
                    tt, ti = t_val, f_val
                
                stat.write("🎨 الصورة...")
                fi = None
                if ti:
                    fi = process_img(ti, iu, crop_logo, logo_ratio, apply_mirror, red_factor)
                    if fi: st.image(fi, width=400)
                
                stat.write(f"✍️ الصياغة ({target_language})...")
                rai = ai_rewrite(tt, api_key, target_language)
                
                if "Error" in rai: st.error(rai)
                else:
                    tit, bod = "", ""
                    if "###SPLIT###" in rai:
                        p = rai.split("###SPLIT###")
                        tit, bod = p[0], p[1]
                    else:
                        l = rai.split('\n')
                        tit, bod = l[0], "\n".join(l[1:])
                    
                    tit = clean_text(tit)
                    bod = clean_text(bod)
                    st.success(f"📌 {tit}")
                    st.markdown(bod)
                    
                    stat.write("🚀 الرفع...")
                    r = wp_up_clean(fi, tit, bod, wp_url, wp_user, wp_password)
                    if r.status_code == 201:
                        st.balloons()
                        st.success(f"تم! [المعاينة]({r.json()['link']})")
                    else: st.error(r.text)
            except Exception as e:
                st.error(f"Error: {e}")