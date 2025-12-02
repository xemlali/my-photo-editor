import streamlit as st
import time

# --- فحص المكتبات قبل البدء ---
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
    st.error(f"❌ خطأ كبير: مكتبة ناقصة! التفاصيل: {e}")
    st.stop()

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="المحرر المباشر", layout="wide", page_icon="⚡")

# --- 2. القائمة الجانبية ---
with st.sidebar:
    st.header("1. البيانات السرية")
    api_key = st.text_input("مفتاح Gemini API", type="password")
    wp_url = st.text_input("رابط الموقع", "https://driouchcity.com")
    wp_user = st.text_input("اسم المستخدم")
    wp_password = st.text_input("كلمة مرور التطبيق", type="password")
    
    st.divider()
    st.header("2. إعدادات الصورة")
    crop_logo = st.checkbox("قص اللوغو", value=True)
    red_factor = st.slider("درجة الاحمرار", 0.0, 0.5, 0.10)

# --- 3. الدوال (المحرك) ---
def resize_fixed(image):
    target_w, target_h = 768, 432
    current_w, current_h = image.size
    target_ratio = target_w / target_h
    current_ratio = current_w / current_h
    
    if current_ratio > target_ratio:
        new_h = target_h
        new_w = int(new_h * current_ratio)
        img = image.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        img = img.crop((left, 0, left + target_w, target_h))
    else:
        new_w = target_w
        new_h = int(new_w / current_ratio)
        img = image.resize((new_w, new_h), Image.LANCZOS)
        top = (new_h - target_h) // 2
        img = img.crop((0, top, target_w, top + target_h))
    return img

def process_img(source, is_url, do_crop, red_val):
    try:
        if is_url:
            resp = requests.get(source, stream=True, timeout=10)
            img = Image.open(resp.raw)
        else:
            img = Image.open(source)
            
        if img.mode != 'RGB': img = img.convert('RGB')
        
        # قص اللوغو
        if do_crop:
            w, h = img.size
            img = img.crop((0, 0, w, int(h * 0.88)))
            
        # قلب
        img = ImageOps.mirror(img)
        
        # أبعاد ثابتة
        img = resize_fixed(img)
        
        # ألوان
        img = ImageEnhance.Color(img).enhance(1.5)
        img = ImageEnhance.Contrast(img).enhance(1.1)
        
        # المسحة الحمراء
        overlay = Image.new('RGB', img.size, (150, 0, 0))
        img = Image.blend(img, overlay, alpha=red_val)
        
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=95)
        return buf.getvalue()
    except Exception as e:
        st.error(f"خطأ في الصورة: {e}")
        return None

def ai_rewrite(txt, key):
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        prompt = f"""
        بصفتك رئيس تحرير، أعد صياغة هذا الخبر:
        1. عنوان واحد جذاب جداً (بدون رموز).
        2. متن قصصي بشري وحيوي.
        3. تجنب لغة الروبوتات.
        النص: {txt[:8000]}
        """
        resp = model.generate_content(prompt)
        return resp.text
    except Exception as e:
        return f"Error: {e}"

def wp_upload(img_bytes, title, content, vids, url, user, pwd):
    creds = f"{user}:{pwd}"
    token = base64.b64encode(creds.encode()).decode('utf-8')
    head = {'Authorization': f'Basic {token}'}
    
    mid = 0
    if img_bytes:
        h_img = head.copy()
        h_img.update({'Content-Disposition': 'attachment; filename=news.jpg', 'Content-Type': 'image/jpeg'})
        try:
            r = requests.post(f"{url}/wp-json/wp/v2/media", headers=h_img, data=img_bytes)
            if r.status_code == 201: mid = r.json()['id']
        except: pass

    final_body = content
    if vids:
        final_body += "\n\n<h3>فيديو:</h3>" + "\n".join(vids)

    h_post = head.copy()
    h_post['Content-Type'] = 'application/json'
    data = {'title': title, 'content': final_body, 'status': 'draft', 'featured_media': mid}
    return requests.post(f"{url}/wp-json/wp/v2/posts", headers=h_post, json=data)

# --- 4. الواجهة والتشغيل المباشر ---
st.title("⚡ المحرر المباشر")

tab1, tab2 = st.tabs(["جلب رابط", "رفع يدوي"])

# متغيرات لتخزين المدخلات
mode = None
link_val = ""
file_val = None
text_val = ""

with tab1:
    link_val = st.text_input("ضع الرابط هنا:")
    if st.button("🚀 تنفيذ الرابط"):
        mode = "link"

with tab2:
    file_val = st.file_uploader("الصورة")
    text_val = st.text_area("النص")
    if st.button("🚀 تنفيذ اليدوي"):
        mode = "manual"

# --- منطقة التنفيذ (خارج الأزرار لضمان التشغيل) ---
if mode:
    # 1. التحقق من البيانات
    if not api_key or not wp_password:
        st.error("⛔ توقف! نسيت إدخال كلمة السر أو مفتاح API في القائمة الجانبية.")
    else:
        status = st.container()
        status.info("⏳ بدأ العمل... تابع الرسائل بالأسفل 👇")
        
        try:
            # تجهيز البيانات
            target_txt = ""
            target_img = None
            is_url = False
            vids = []

            if mode == "link":
                if not link_val:
                    st.error("الرابط فارغ!")
                    st.stop()
                status.write("1️⃣ جلب بيانات الرابط...")
                art = Article(link_val)
                art.download()
                art.parse()
                target_txt = art.text
                target_img = art.top_image
                vids = art.movies
                is_url = True
            else:
                target_txt = text_val
                target_img = file_val
                is_url = False

            # معالجة الصورة
            status.write("2️⃣ هندسة الصورة (ألوان + قص)...")
            final_img = None
            if target_img:
                final_img = process_img(target_img, is_url, crop_logo, red_factor)
                if final_img:
                    st.image(final_img, caption="تمت المعالجة (768x432)", width=400)
            
            # معالجة النص
            status.write("3️⃣ الذكاء الاصطناعي يكتب...")
            ai_out = ai_rewrite(target_txt, api_key)
            
            if "Error" in ai_out:
                st.error(f"خطأ AI: {ai_out}")
            else:
                # تنظيف
                clean = ai_out.replace('**', '').replace('##', '')
                lines = clean.split('\n')
                tit = next((l for l in lines if l.strip()), "عنوان")
                tit = re.sub(r'[^\w\s\u0600-\u06FF]', '', tit) # إزالة رموز غريبة من العنوان
                body = "\n".join([l for l in lines if l.strip() != tit])

                st.success(f"✅ العنوان: {tit}")
                st.markdown(body)

                # النشر
                status.write("4️⃣ الإرسال للموقع...")
                res = wp_upload(final_img, tit, body, vids, wp_url, wp_user, wp_password)
                
                if res.status_code == 201:
                    st.balloons()
                    lnk = res.json()['link']
                    st.success(f"🎉 تم النشر بنجاح! [اضغط هنا للمعاينة]({lnk})")
                else:
                    st.error(f"فشل النشر: {res.text}")

        except Exception as e:
            st.error(f"حدث خطأ غير متوقع: {e}")