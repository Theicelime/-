import streamlit as st
import numpy as np
from PIL import Image
from sklearn.cluster import KMeans
import colorsys

# ==========================================
# 1. 核心逻辑函数
# ==========================================

def extract_colors_kmeans(image, n_colors=7):
    """
    使用 K-Means 聚类算法从图片中提取主色调
    """
    # 缩放图片以提高计算速度，同时减少噪点影响
    img_small = image.resize((150, 150))
    ar = np.asarray(img_small)
    shape = ar.shape
    
    # 去除 Alpha 通道 (如果是 PNG)
    if len(shape) == 3 and shape[2] > 3:
        ar = ar[:, :, :3]
    
    # 展平数组
    ar = ar.reshape(np.product(shape[:2]), shape[2])
    
    # 聚类
    kmeans = KMeans(n_clusters=n_colors, n_init=10, max_iter=300)
    kmeans.fit(ar)
    colors = kmeans.cluster_centers_ # 得到浮点数 RGB
    
    # 转为整数并返回列表
    return [tuple(map(int, c)) for c in colors]

def sort_colors(colors, method="亮度 (暗 -> 亮)"):
    """
    关键步骤：对颜色进行排序以形成渐变
    """
    if method == "亮度 (暗 -> 亮)":
        # 公式: 0.299R + 0.587G + 0.114B (感知亮度)
        return sorted(colors, key=lambda c: c[0]*0.299 + c[1]*0.587 + c[2]*0.114)
    
    elif method == "亮度 (亮 -> 暗)":
        return sorted(colors, key=lambda c: c[0]*0.299 + c[1]*0.587 + c[2]*0.114, reverse=True)
    
    elif method == "色相 (彩虹顺序)":
        # 转换为 HSV 的 H 进行排序
        return sorted(colors, key=lambda c: colorsys.rgb_to_hsv(c[0]/255, c[1]/255, c[2]/255)[0])
    
    elif method == "饱和度 (灰 -> 鲜艳)":
        return sorted(colors, key=lambda c: colorsys.rgb_to_hsv(c[0]/255, c[1]/255, c[2]/255)[1])
    
    else: # 原始聚类顺序 (通常是随机的)
        return colors

def rgb_to_hex(rgb):
    return '#{:02x}{:02x}{:02x}'.format(*rgb)

def generate_clr_content(colors_rgb):
    """
    生成 ArcGIS CLR 文件内容
    格式: Index R G B
    """
    content = ""
    for idx, (r, g, b) in enumerate(colors_rgb):
        content += f"{idx + 1} {r} {g} {b}\n"
    return content

def get_gradient_css(colors_rgb):
    hex_colors = [rgb_to_hex(c) for c in colors_rgb]
    return f"linear-gradient(to right, {', '.join(hex_colors)})"

# ==========================================
# 2. 页面布局
# ==========================================

st.set_page_config(page_title="GIS Gradient Maker", page_icon="🌈", layout="centered")

st.markdown("""
<style>
    .stApp {background-color: #f8f9fa;}
    .color-box {
        width: 100%;
        height: 60px;
        border-radius: 8px;
        margin-top: 10px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border: 1px solid #ddd;
    }
    .hex-code {
        font-family: monospace;
        font-size: 12px;
        color: #555;
        background: #eee;
        padding: 2px 4px;
        border-radius: 4px;
        margin-right: 4px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🌈 图片转 GIS 渐变色带工具")
st.markdown("上传一张电影截图或风景照，自动提取主题色并生成 **ArcGIS .clr** 文件。")

# --- 侧边栏设置 ---
with st.sidebar:
    st.header("⚙️ 参数设置")
    
    n_colors = st.slider("提取颜色数量 (节点数)", min_value=3, max_value=15, value=7, help="GIS 色带通常使用 5-9 个节点效果最好")
    
    sort_method = st.selectbox(
        "渐变排序逻辑 (关键步骤)",
        ["亮度 (暗 -> 亮)", "亮度 (亮 -> 暗)", "色相 (彩虹顺序)", "饱和度 (灰 -> 鲜艳)", "原始提取顺序"],
        index=0,
        help="为了让提取的颜色形成平滑的过渡，必须对颜色进行排序。"
    )

# --- 主体区域 ---
uploaded_file = st.file_uploader("📤 请上传图片 (JPG / PNG)", type=['jpg', 'jpeg', 'png'])

if uploaded_file is not None:
    # 1. 显示原图
    image = Image.open(uploaded_file)
    st.image(image, caption="原始图片", use_container_width=True)
    
    with st.spinner("正在分析色彩并构建渐变..."):
        # 2. 提取颜色
        raw_colors = extract_colors_kmeans(image, n_colors=n_colors)
        
        # 3. 排序 (构建渐变)
        sorted_colors = sort_colors(raw_colors, sort_method)
        
        # 4. 生成预览
        gradient_css = get_gradient_css(sorted_colors)
        
        st.divider()
        st.subheader("🎨 生成的渐变色带")
        
        # 渲染渐变条
        st.markdown(f'<div class="color-box" style="background: {gradient_css};"></div>', unsafe_allow_html=True)
        
        # 显示色值详情
        cols = st.columns(len(sorted_colors))
        for idx, color in enumerate(sorted_colors):
            hex_val = rgb_to_hex(color)
            # 在每个小列中显示颜色块
            cols[idx].markdown(f'<div style="background-color:{hex_val}; height:20px; width:100%; border-radius:4px;"></div>', unsafe_allow_html=True)
            cols[idx].caption(f"{hex_val}")

    # 5. 下载区域
    st.divider()
    st.subheader("📥 下载结果")
    
    col1, col2 = st.columns(2)
    
    # 下载 CLR
    clr_content = generate_clr_content(sorted_colors)
    file_name = uploaded_file.name.split('.')[0] + f"_{n_colors}c.clr"
    
    with col1:
        st.download_button(
            label="📄 下载 ArcGIS .clr 文件",
            data=clr_content,
            file_name=file_name,
            mime="text/plain",
            type="primary",
            use_container_width=True
        )
        st.caption("适用：ArcGIS Pro, ArcMap (Stretch Renderer)")

    # 额外功能：生成 JSON (如果你想加回之前的库)
    with col2:
        json_entry = {
            "name": uploaded_file.name.split('.')[0],
            "category": "Extracted",
            "tags": ["Image"],
            "colors": [rgb_to_hex(c) for c in sorted_colors]
        }
        import json
        st.download_button(
            label="📦 下载 JSON 配置",
            data=json.dumps([json_entry], indent=2),
            file_name="palette_config.json",
            mime="application/json",
            use_container_width=True
        )
        st.caption("适用：导入到之前的色带库网页中")

else:
    # 空状态提示
    st.info("👋 等待图片上传...")
    st.markdown("""
    #### 💡 小贴士：如何获得好看的渐变？
    1. **亮度排序 (暗 -> 亮)**：最适合 **DEM (高程图)** 或 **夜光数据**。深色表示低值，亮色表示高值。
    2. **色相排序**：适合 **土地利用分类** 或 **植被指数 (NDVI)**，颜色变化丰富。
    3. **颜色数量**：不要太多，**5-7 个** 颜色通常能产生最平滑、自然的过渡。
    """)
