import streamlit as st
from newspaper import Article
import requests
import base64
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps
import io
import numpy as np

# --- إعدادات الصفحة ---
st.set_page_config(page_title="المحرر الذكي الشامل", layout="wide", page_icon="🚀")
st.title("🚀 المحرر الصحفي الشامل (AI + معالجة صور)")

# --- القائمة الجانبية ---
with st.sidebar:
    st.header("1. إعدادات الموقع")
    wp_url = st.text_input("رابط الموقع", "https://driouchcity.com")
    wp_user = st.text_input("اسم المستخدم (WordPress)")
    wp_password = st.text_input("كلمة مرور التطبيق", type="password")
    
    st.divider()
    st.header("2. إعدادات الذكاء الاصطناعي")
    # احصل على المفتاح من: https://aistudio.google.com/app/apikey
    api_key = st.text_input("مفتاح Gemini API", type="password")

# --- دوال معالجة الصور (الفلاتر) ---
def create_vignette(image, corner_darkness=180):
    # إضافة هالة سوداء سينمائية للأطراف
    if image.mode != 'RGB':
        image = image.convert('RGB')
    width, height = image.size
    
    # إنشاء قناع التدرج
    x = np.linspace(-1, 1, width)
    y = np.linspace(-1, 1, height)
    X, Y = np.meshgrid(x, y)
    radius = np.sqrt(X**2 + Y**2)
    radius = radius / np.max(radius)
    alpha = 1 - radius
    alpha = np.power(alpha, 1.5) # التحكم في نعومة التدرج
    
    # تطبيق القناع
    vignette_mask = Image.fromarray((alpha * 255).astype('uint8'), mode='L')
    black_layer = Image.new('RGB', (width, height), 'black')
    return Image.composite(image, black_layer, vignette_mask)

def process_image_for_news(image_url):
    try:
        # 1. تحميل الصورة
        response = requests.get(image_url, stream=True)
        img = Image.open(response.raw)
        
        # 2. تحسين الألوان (Saturation)
        converter = ImageEnhance.Color(img)
        img = converter.enhance(1.4) # زيادة التشبع 40%
        
        # 3. تحسين التباين (Contrast)
        converter = ImageEnhance.Contrast(img)
        img = converter.enhance(1.2) # زيادة التباين 20%
        
        # 4. تحسين الحدة (Sharpness)
        converter = ImageEnhance.Sharpness(img)
        img = converter.enhance(1.3)
        
        # 5. إضافة الفينييت (تأثير انستغرام/سينمائي)
        img = create_vignette(img)
        
        # تحويل النتيجة لملف جاهز للرفع
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=90)
        return buf.getvalue()
    except Exception as e:
        st.error(f"خطأ في معالجة الصورة: {e}")
        return None

# --- دوال الذكاء الاصطناعي (إعادة الصياغة) ---
def rewrite_article_ai(original_text, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    أنت صحفي محترف ومدقق لغوي خبير (Copywriter). قم بإعادة صياغة النص التالي ليكون مقالاً صحفياً جاهزاً للنشر.
    
    الشروط الصارمة:
    1. **الأسلوب:** صحفي، رصين، بشري تماماً، خالي من الحشو والمبالغات (مثل: "في خطوة غير مسبوقة"، "مما لا شك فيه").
    2. **السيو (SEO):** استخدم الكلمات المفتاحية في الفقرة الأولى بشكل طبيعي.
    3. **العنوان:** اكتب عنواناً واحداً فقط في السطر الأول، يكون جذاباً جداً للنقر (Click-worthy) ويحتوي على الكلمة المفتاحية، لكن دون كذب.
    4. **الهيكل:** قسم النص إلى فقرات قصيرة (3-4 أسطر).
    5. **اللغة:** عربية سليمة وقوية.
    
    النص الأصلي:
    {original_text[:5000]}
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"خطأ AI: {e}"

# --- دوال ووردبريس ---
def upload_image_bytes(image_data, wp_url, wp_user, wp_password):
    credentials = f"{wp_user}:{wp_password}"
    token = base64.b64encode(credentials.encode()).decode('utf-8')
    headers = {
        'Authorization': f'Basic {token}',
        'Content-Disposition': 'attachment; filename=processed-news.jpg',
        'Content-Type': 'image/jpeg'
    }
    response = requests.post(f"{wp_url}/wp-json/wp/v2/media", headers=headers, data=image_data)
    if response.status_code == 201:
        return response.json()['id']
    return None

def create_wp_post(title, content, image_id, wp_url, wp_user, wp_password):
    credentials = f"{wp_user}:{wp_password}"
    token = base64.b64encode(credentials.encode()).decode('utf-8')
    headers = {'Authorization': f'Basic {token}', 'Content-Type': 'application/json'}
    
    post = {
        'title': title,
        'content': content,
        'status': 'draft',
        'featured_media': image_id
    }
    return requests.post(f"{wp_url}/wp-json/wp/v2/posts", headers=headers, json=post)

# --- الواجهة الرئيسية ---
url_input = st.text_input("🔗 ضع رابط الخبر الأصلي هنا:")

if st.button("✨ تشغيل المعالج السحري"):
    if not api_key or not wp_password:
        st.warning("⚠️ تأكد من إدخال مفتاح API وكلمة مرور التطبيق في القائمة الجانبية.")
    else:
        status_box = st.status("جاري العمل... يرجى الانتظار", expanded=True)
        
        try:
            # 1. جلب الخبر
            status_box.write("📥 جاري سحب الخبر من المصدر...")
            article = Article(url_input)
            article.download()
            article.parse()
            
            # 2. معالجة الصورة
            status_box.write("🎨 جاري تحسين الصورة وإضافة التأثيرات...")
            if article.top_image:
                processed_image = process_image_for_news(article.top_image)
                st.image(processed_image, caption="الصورة بعد المعالجة (ألوان + فينييت)", width=400)
            else:
                processed_image = None
                st.warning("لم يتم العثور على صورة في الرابط.")

            # 3. إعادة الصياغة
            status_box.write("🤖 الذكاء الاصطناعي يعيد صياغة الخبر الآن...")
            ai_result = rewrite_article_ai(article.text, api_key)
            
            # فصل العنوان عن المتن (نفترض أن السطر الأول هو العنوان)
            lines = ai_result.split('\n')
            final_title = lines[0].replace('*', '').strip() # تنظيف الرموز
            final_content = "\n".join(lines[1:])
            
            st.subheader("📝 النص المعاد صياغته:")
            st.text_area("العنوان المقترح", final_title)
            st.markdown(final_content) # عرض النص بتنسيق جميل

            # 4. النشر
            status_box.write("🚀 جاري الرفع لموقعك...")
            
            # رفع الصورة أولاً
            media_id = 0
            if processed_image:
                media_id = upload_image_bytes(processed_image, wp_url, wp_user, wp_password)
            
            # رفع المقال
            res = create_wp_post(final_title, final_content, media_id, wp_url, wp_user, wp_password)
            
            if res.status_code == 201:
                status_box.update(label="✅ تمت المهمة بنجاح!", state="complete", expanded=False)
                st.balloons()
                st.success(f"تم إنشاء المسودة بنجاح! [رابط المعاينة]({res.json()['link']})")
            else:
                status_box.update(label="❌ حدث خطأ في النشر", state="error")
                st.error(res.text)

        except Exception as e:
            st.error(f"حدث خطأ غير متوقع: {e}")