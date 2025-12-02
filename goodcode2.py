import streamlit as st
from newspaper import Article
import requests
import base64
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps, ImageBlend
import io
import re

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="المحرر الاحترافي 5.0", layout="wide", page_icon="📰")

# --- 2. القائمة الجانبية ---
with st.sidebar:
    st.header("⚙️ الإعدادات التقنية")
    wp_url = st.text_input("رابط الموقع", "https://driouchcity.com")
    wp_user = st.text_input("اسم المستخدم")
    wp_password = st.text_input("كلمة مرور التطبيق", type="password")
    st.divider()
    api_key = st.text_input("مفتاح Gemini API", type="password")
    
    st.divider()
    st.header("🎨 هندسة الصورة")
    remove_logo = st.checkbox("قص اللوغو السفلي", value=True)
    # خيار قوة اللون الأحمر (الافتراضي خفيف جداً 0.15)
    red_intensity = st.slider("كثافة المسحة الحمراء", 0.0, 0.5, 0.10, 0.05)

# --- 3. الدوال البرمجية المتقدمة ---

def resize_to_exact_dimensions(image, target_w=768, target_h=432):
    """
    دالة لضمان أن الصورة تخرج بالأبعاد المطلوبة بالضبط (768x432)
    عن طريق ملء الإطار والقص من المنتصف (Center Crop)
    """
    current_w, current_h = image.size
    
    # حساب النسبة
    target_ratio = target_w / target_h
    current_ratio = current_w / current_h
    
    if current_ratio > target_ratio:
        # الصورة أعرض من المطلوب: نضبط الارتفاع ونقص العرض
        new_h = target_h
        new_w = int(new_h * current_ratio)
        img_resized = image.resize((new_w, new_h), Image.LANCZOS)
        
        # القص من الوسط
        left = (new_w - target_w) // 2
        img_final = img_resized.crop((left, 0, left + target_w, target_h))
    else:
        # الصورة أطول من المطلوب: نضبط العرض ونقص الارتفاع
        new_w = target_w
        new_h = int(new_w / current_ratio)
        img_resized = image.resize((new_w, new_h), Image.LANCZOS)
        
        # القص من الوسط
        top = (new_h - target_h) // 2
        img_final = img_resized.crop((0, top, target_w, top + target_h))
        
    return img_final

def process_image_pro(image_input, crop_logo, red_factor):
    try:
        # تحميل الصورة
        if isinstance(image_input, str): 
            response = requests.get(image_input, stream=True)
            img = Image.open(response.raw)
        else: 
            img = Image.open(image_input)
        
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # 1. قص اللوغو (أولاً وقبل أي شيء)
        if crop_logo:
            w, h = img.size
            # نقص 12% من الأسفل
            img = img.crop((0, 0, w, int(h * 0.88)))

        # 2. القلب الأفقي (Mirror)
        img = ImageOps.mirror(img)

        # 3. ضبط الأبعاد الصارم (768x432)
        img = resize_to_exact_dimensions(img, 768, 432)

        # 4. المعالجة اللونية
        # زيادة التشبع اللوني (Saturation) بشكل ملحوظ
        img = ImageEnhance.Color(img).enhance(1.5) 
        # زيادة التباين قليلاً
        img = ImageEnhance.Contrast(img).enhance(1.1)
        
        # 5. إضافة المسحة الحمراء الخفيفة جداً (Red Tint)
        # ننشئ طبقة حمراء ونخلطها بنسبة ضئيلة جداً (Overlay)
        red_layer = Image.new('RGB', img.size, (150, 0, 0)) # أحمر قاني
        # red_factor يتحكم في الشفافية (0.10 يعني 10% فقط أحمر)
        img = Image.blend(img, red_layer, alpha=red_factor)

        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=95)
        return buf.getvalue()
    except Exception as e:
        st.error(f"خطأ الصورة: {e}")
        return None

def clean_text(text):
    """تنظيف النصوص من رموز الماركداون"""
    text = text.replace('**', '').replace('##', '').replace('__', '')
    text = re.sub(r'^\s*[\#\*\-]+\s*', '', text) # حذف الرموز في بداية السطر
    return text.strip()

def rewrite_article_pro(text, key):
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # هندسة الأمر (Prompt Engineering) متقدمة جداً
        prompt = f"""
        أنت رئيس تحرير في وكالة أنباء كبرى. مهمتك صياغة هذا الخبر للنشر.
        
        التعليمات الصارمة (Style Guide):
        1. **الأسلوب:** بشري 100%. اكتب بحيوية، استخدم جملاً قصيرة وقوية. ابتعد تماماً عن الركاكة والرتابة.
        2. **الممنوعات:** يُحظر استخدام عبارات الذكاء الاصطناعي مثل: "جدير بالذكر"، "مما لا شك فيه"، "في خطوة تهدف"، "تجدر الإشارة".
        3. **العنوان:** سطر واحد فقط. يجب أن يكون "ذكياً" ومثيراً للفضول (Clickbait) لكن صادقاً. لا تضع أي رموز مثل # أو *.
        4. **الهيكل:** ادخل في صلب الموضوع مباشرة (In medias res).
        
        النص الخام:
        {text[:9000]}
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {e}"

def upload_to_wp_pro(img_data, title, content, videos, url, user, password):
    creds = f"{user}:{password}"
    token = base64.b64encode(creds.encode()).decode('utf-8')
    headers_auth = {'Authorization': f'Basic {token}'}

    # 1. رفع الصورة
    media_id = 0
    if img_data:
        headers_img = headers_auth.copy()
        headers_img['Content-Disposition'] = 'attachment; filename=news-768x432.jpg'
        headers_img['Content-Type'] = 'image/jpeg'
        try:
            r = requests.post(f"{url}/wp-json/wp/v2/media", headers=headers_img, data=img_data)
            if r.status_code == 201:
                media_id = r.json()['id']
        except:
            pass

    # 2. تجهيز المحتوى (إضافة الفيديوهات إن وجدت)
    final_content = content
    if videos:
        final_content += "\n\n<h3>فيديوهات ذات صلة:</h3>"
        for video_url in videos:
            # ووردبريس يحول روابط يوتيوب تلقائياً إلى مشغل فيديو
            final_content += f"\n{video_url}\n"

    # 3. رفع المقال
    headers_post = headers_auth.copy()
    headers_post['Content-Type'] = 'application/json'
    post_data = {
        'title': title,
        'content': final_content,
        'status': 'draft',
        'featured_media': media_id
    }
    return requests.post(f"{url}/wp-json/wp/v2/posts", headers=headers_post, json=post_data)

# --- 4. الواجهة والتشغيل ---
st.title("📰 المحرر الصحفي (DriouchCity Pro)")
st.markdown("---")

tab1, tab2 = st.tabs(["🔗 رابط خبر", "📝 يدوي"])

with tab1:
    url_input = st.text_input("رابط الخبر:")
    btn_link = st.button("تنفيذ المعالجة", type="primary")

with tab2:
    col_img, col_txt = st.columns([1, 2])
    with col_img: uploaded_img = st.file_uploader("صورة", type=['jpg','png','jpeg'])
    with col_txt: uploaded_txt = st.text_area("النص", height=150)
    btn_manual = st.button("تنفيذ اليدوي", type="primary")

# المنطق الموحد
target_text = ""
target_image = None
target_videos = [] # قائمة لتخزين روابط الفيديو
start = False

if btn_link and url_input:
    start = True
    with st.spinner("جلب البيانات..."):
        try:
            art = Article(url_input)
            art.download()
            art.parse()
            target_text = art.text
            target_image = art.top_image
            target_videos = art.movies # جلب روابط الفيديو
        except Exception as e:
            st.error(f"فشل الجلب: {e}")
            start = False

elif btn_manual and uploaded_img and uploaded_txt:
    start = True
    target_text = uploaded_txt
    target_image = uploaded_img

if start:
    if not api_key or not wp_password:
        st.error("البيانات ناقصة!")
    else:
        with st.status("جاري العمل... ⏳", expanded=True) as status:
            try:
                # 1. الصورة (768x432 + مسحة حمراء)
                status.write("🎨 هندسة الصورة (768x432)...")
                final_img = None
                if target_image:
                    final_img = process_image_pro(target_image, remove_logo, red_intensity)
                    if final_img:
                        st.image(final_img, caption="768x432 Pixel Perfect", width=400)
                
                # 2. النص (البشري)
                status.write("✍️ صياغة صحفية بشرية...")
                ai_res = rewrite_article_pro(target_text, api_key)
                
                if "Error" in ai_res:
                    st.error(ai_res)
                else:
                    # تنظيف شامل
                    clean_res = clean_text(ai_res)
                    lines = clean_res.split('\n')
                    
                    # استخراج العنوان بذكاء (أول سطر فيه نص)
                    tit = next((l for l in lines if l.strip()), "عنوان")
                    # تنظيف العنوان مرة أخرى للتأكد
                    tit = clean_text(tit)
                    
                    # المحتوى هو الباقي
                    body = "\n".join([l for l in lines if l.strip() != tit])
                    
                    st.success("العنوان المقترح:")
                    st.text_input("", tit, label_visibility="collapsed")
                    st.markdown(body)
                    
                    if target_videos:
                        st.info(f"تم العثور على {len(target_videos)} فيديو سيتم تضمينها.")

                    # 3. النشر
                    status.write("🚀 الرفع للموقع...")
                    res = upload_to_wp_pro(final_img, tit, body, target_videos, wp_url, wp_user, wp_password)
                    
                    if res.status_code == 201:
                        status.update(label="✅ تم!", state="complete", expanded=False)
                        lnk = res.json()['link']
                        st.balloons()
                        st.success(f"المقال جاهز! [رابط المعاينة]({lnk})")
                    else:
                        st.error(f"خطأ ووردبريس: {res.text}")

            except Exception as e:
                st.error(f"حدث خطأ: {e}")