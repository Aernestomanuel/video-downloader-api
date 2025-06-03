from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import subprocess
import json
import re
from urllib.parse import urlparse, parse_qs
import threading
import time

app = Flask(__name__)
CORS(app)

# Configurações globais
TEMP_DIR = tempfile.mkdtemp()
MAX_FILE_AGE = 3600  # 1 hora em segundos

# Lista de sites de conteúdo adulto (domínios a bloquear)
ADULT_CONTENT_DOMAINS = {
    'pornhub.com', 'xvideos.com', 'xnxx.com', 'redtube.com', 'youporn.com',
    'tube8.com', 'spankbang.com', 'xhamster.com', 'beeg.com', 'chaturbate.com',
    'cam4.com', 'bongacams.com', 'stripchat.com', 'livejasmin.com', 'camsoda.com',
    'sex.com', 'porn.com', 'motherless.com', 'heavy-r.com', 'eporner.com',
    'txxx.com', 'drtuber.com', 'nuvid.com', 'alphaporno.com', 'fapdu.com',
    'gotporn.com', 'sunporno.com', 'vjav.com', 'javhd.com', 'javmost.com',
    'onlyfans.com', 'manyvids.com', 'clips4sale.com', 'iwantclips.com',
    'adultdvdempire.com', 'brazzers.com', 'realitykings.com', 'bangbros.com',
    'naughtyamerica.com', 'digitalplayground.com', 'twistys.com', 'babes.com',
    'myfreecams.com', 'cams.com', 'flirt4free.com', 'streamate.com'
}

# Sites suportados pelo yt-dlp (principais plataformas de vídeo legítimas)
SUPPORTED_PLATFORMS = {
    # Vídeo Principal
    'youtube.com': 'YouTube',
    'youtu.be': 'YouTube',
    'vimeo.com': 'Vimeo',
    'dailymotion.com': 'Dailymotion',
    
    # Redes Sociais
    'facebook.com': 'Facebook',
    'instagram.com': 'Instagram',
    'twitter.com': 'Twitter (X)',
    'x.com': 'Twitter (X)',
    'tiktok.com': 'TikTok',
    'twitch.tv': 'Twitch',
    'snapchat.com': 'Snapchat',
    
    # Música/Áudio
    'soundcloud.com': 'SoundCloud',
    'bandcamp.com': 'Bandcamp',
    'mixcloud.com': 'Mixcloud',
    'spotify.com': 'Spotify (podcasts)',
    'anchor.fm': 'Anchor',
    'spreaker.com': 'Spreaker',
    'podbean.com': 'Podbean',
    'audiomack.com': 'Audiomack',
    
    # Educação
    'coursera.org': 'Coursera',
    'udemy.com': 'Udemy',
    'khan-academy.org': 'Khan Academy',
    'ted.com': 'TED Talks',
    'mit.edu': 'MIT OpenCourseWare',
    'harvard.edu': 'Harvard',
    'stanford.edu': 'Stanford',
    'edx.org': 'edX',
    'futurelearn.com': 'FutureLearn',
    'skillshare.com': 'Skillshare',
    
    # Notícias
    'bbc.co.uk': 'BBC',
    'cnn.com': 'CNN',
    'reuters.com': 'Reuters',
    'bloomberg.com': 'Bloomberg',
    'cnbc.com': 'CNBC',
    'npr.org': 'NPR',
    'pbs.org': 'PBS',
    'aljazeera.com': 'Al Jazeera',
    'dw.com': 'Deutsche Welle',
    'euronews.com': 'Euronews',
    
    # TV Internacional
    'arte.tv': 'Arte',
    'france.tv': 'France TV',
    'rai.it': 'RAI',
    'rtve.es': 'RTVE',
    'zdf.de': 'ZDF',
    'ard.de': 'ARD',
    'nrk.no': 'NRK',
    'svt.se': 'SVT',
    'yle.fi': 'YLE',
    'cbc.ca': 'CBC',
    'abc.net.au': 'ABC Australia',
    'sbs.com.au': 'SBS',
    'tvp.pl': 'TVP',
    'rtp.pt': 'RTP',
    'globo.com': 'Globo',
    'record.tv': 'Record TV',
    'sbt.com.br': 'SBT',
    'band.com.br': 'Band',
    
    # Alternativas
    'bitchute.com': 'BitChute',
    'rumble.com': 'Rumble',
    'odysee.com': 'Odysee',
    'brighteon.com': 'Brighteon',
    'lbry.tv': 'LBRY',
    'minds.com': 'Minds',
    'gab.com': 'Gab TV',
    'gettr.com': 'Gettr',
    'parler.com': 'Parler',
    'locals.com': 'Locals',
    
    # Desporto
    'espn.com': 'ESPN',
    'nba.com': 'NBA',
    'fifa.com': 'FIFA',
    'olympics.com': 'Olympics',
    'ufc.com': 'UFC',
    'mlb.com': 'MLB',
    'nfl.com': 'NFL',
    'uefa.com': 'UEFA',
    
    # Documentários
    'discovery.com': 'Discovery',
    'nationalgeographic.com': 'National Geographic',
    'history.com': 'History Channel',
    'smithsonian.com': 'Smithsonian',
    'archive.org': 'Internet Archive'
}

def cleanup_old_files():
    """Remove ficheiros antigos do directório temporário"""
    try:
        current_time = time.time()
        for filename in os.listdir(TEMP_DIR):
            file_path = os.path.join(TEMP_DIR, filename)
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getctime(file_path)
                if file_age > MAX_FILE_AGE:
                    os.remove(file_path)
    except Exception as e:
        print(f"Erro na limpeza: {e}")

def extract_domain(url):
    """Extrai o domínio de um URL"""
    try:
        parsed = urlparse(url.lower().strip())
        domain = parsed.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return None

def is_adult_content(url):
    """Verifica se o URL é de conteúdo adulto"""
    domain = extract_domain(url)
    if not domain:
        return False
    
    if domain in ADULT_CONTENT_DOMAINS:
        return True
    
    for adult_domain in ADULT_CONTENT_DOMAINS:
        if domain.endswith('.' + adult_domain):
            return True
    
    adult_keywords = ['porn', 'sex', 'xxx', 'adult', 'cam', 'strip', 'nude', 'nsfw']
    for keyword in adult_keywords:
        if keyword in domain:
            return True
    
    return False

def get_platform_name(url):
    """Identifica a plataforma do vídeo"""
    domain = extract_domain(url)
    if not domain:
        return "Desconhecido"
    
    for supported_domain, platform_name in SUPPORTED_PLATFORMS.items():
        if domain == supported_domain or domain.endswith('.' + supported_domain):
            return platform_name
    
    if 'youtube' in domain:
        return 'YouTube'
    elif 'vimeo' in domain:
        return 'Vimeo'
    elif 'facebook' in domain or 'fb.com' in domain:
        return 'Facebook'
    elif 'instagram' in domain:
        return 'Instagram'
    elif 'tiktok' in domain:
        return 'TikTok'
    elif 'twitch' in domain:
        return 'Twitch'
    
    return f"Plataforma Suportada ({domain})"

def validate_video_url(url):
    """Valida se é um URL de vídeo suportado"""
    if not url or not isinstance(url, str):
        return False, "URL inválido"
    
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        return False, "URL deve começar com http:// ou https://"
    
    if is_adult_content(url):
        return False, "BLOQUEADO: Conteúdo adulto não permitido"
    
    domain = extract_domain(url)
    if not domain:
        return False, "Domínio inválido"
    
    platform = get_platform_name(url)
    return True, f"URL válido - Plataforma: {platform}"

def get_video_info(url):
    """Obtém informações do vídeo/áudio sem fazer download"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'skip_download': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            platform = get_platform_name(url)
            
            formats = info.get('formats', [])
            has_video = False
            has_audio = False
            audio_only = False
            best_audio_ext = None
            video_formats = []
            audio_formats = []
            
            for fmt in formats:
                vcodec = fmt.get('vcodec', 'none')
                acodec = fmt.get('acodec', 'none')
                ext = fmt.get('ext', 'unknown')
                
                if vcodec and vcodec != 'none':
                    has_video = True
                    video_formats.append({
                        'format_id': fmt.get('format_id'),
                        'ext': ext,
                        'quality': fmt.get('height', 0),
                        'filesize': fmt.get('filesize')
                    })
                
                if acodec and acodec != 'none':
                    has_audio = True
                    audio_formats.append({
                        'format_id': fmt.get('format_id'),
                        'ext': ext,
                        'abr': fmt.get('abr', 0),
                        'filesize': fmt.get('filesize')
                    })
                    
                    if not best_audio_ext or ext in ['mp3', 'aac', 'ogg', 'm4a']:
                        best_audio_ext = ext
            
            audio_only = has_audio and not has_video
            
            audio_platforms = ['soundcloud.com', 'bandcamp.com', 'mixcloud.com', 'anchor.fm', 
                             'spreaker.com', 'podbean.com', 'spotify.com']
            domain = extract_domain(url)
            
            if any(audio_platform in domain for audio_platform in audio_platforms):
                audio_only = True
                has_video = False
            
            title = info.get('title', '').lower()
            description = info.get('description', '').lower()
            podcast_keywords = ['podcast', 'episode', 'ep.', 'música', 'music', 'song', 'track', 
                              'album', 'single', 'audio', 'sound']
            
            is_audio_content = any(keyword in title or keyword in description 
                                 for keyword in podcast_keywords)
            
            if is_audio_content and not has_video:
                audio_only = True
            
            return {
                'id': info.get('id', ''),
                'title': info.get('title', 'Título desconhecido'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'uploader': info.get('uploader', 'Desconhecido'),
                'uploader_id': info.get('uploader_id', ''),
                'view_count': info.get('view_count', 0),
                'upload_date': info.get('upload_date', ''),
                'description': info.get('description', '')[:200] + '...' if info.get('description') else '',
                'platform': platform,
                'webpage_url': info.get('webpage_url', url),
                'available': True,
                'has_video': has_video,
                'has_audio': has_audio,
                'audio_only': audio_only,
                'best_audio_ext': best_audio_ext or 'mp3',
                'video_formats': video_formats[:3],
                'audio_formats': audio_formats[:3],
                'formats_available': len(formats),
                'content_type': 'audio_only' if audio_only else 'video_with_audio' if (has_video and has_audio) else 'video_only' if has_video else 'unknown'
            }
    except Exception as e:
        error_msg = str(e).lower()
        
        if 'private' in error_msg or 'unavailable' in error_msg:
            error_detail = "Conteúdo privado ou indisponível"
        elif 'region' in error_msg or 'blocked' in error_msg:
            error_detail = "Conteúdo bloqueado na sua região"
        elif 'age' in error_msg:
            error_detail = "Conteúdo com restrição de idade"
        elif 'copyright' in error_msg:
            error_detail = "Conteúdo removido por direitos de autor"
        elif 'live' in error_msg:
            error_detail = "Transmissões ao vivo não suportadas"
        else:
            error_detail = f"Erro: {str(e)}"
        
        return {
            'available': False,
            'error': error_detail,
            'platform': get_platform_name(url),
            'has_video': False,
            'has_audio': False,
            'audio_only': False
        }

def download_video(url, format_type='mp4', quality='best', force_audio=False):
    """Descarrega vídeo ou áudio de qualquer plataforma suportada"""
    url_hash = str(abs(hash(url)))[:8]
    
    if force_audio:
        format_type = 'mp3'
    
    if format_type == 'mp3' or format_type in ['aac', 'ogg', 'flac', 'wav']:
        output_template = os.path.join(TEMP_DIR, f'{url_hash}_%(title)s.%(ext)s')
        
        if format_type == 'mp3':
            audio_format = 'mp3'
            audio_quality = '192'
        elif format_type == 'aac':
            audio_format = 'aac'
            audio_quality = '128'
        elif format_type == 'ogg':
            audio_format = 'vorbis'
            audio_quality = '192'
        elif format_type == 'flac':
            audio_format = 'flac'
            audio_quality = '0'
        else:
            audio_format = 'mp3'
            audio_quality = '192'
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': audio_format,
                'preferredquality': audio_quality,
            }],
            'quiet': True,
            'no_warnings': True,
        }
    else:
        output_template = os.path.join(TEMP_DIR, f'{url_hash}_%(title)s.%(ext)s')
        
        if quality == 'hd':
            format_selector = 'best[height<=720]/best[width<=1280]/best'
        else:
            format_selector = 'best[height<=480]/best[width<=854]/best'
            
        ydl_opts = {
            'format': format_selector,
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'writesubtitles': False,
            'writeautomaticsub': False,
        }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'video')
            platform = get_platform_name(url)
            
            if format_type == 'mp4' and force_audio:
                raise Exception(f"[{platform}] Conteúdo apenas disponível em áudio")
            
            ydl.download([url])
            
            expected_ext = format_type
            if format_type in ['mp3', 'aac', 'ogg', 'flac', 'wav']:
                audio_extensions = ['mp3', 'aac', 'ogg', 'flac', 'wav', 'm4a']
                for ext in audio_extensions:
                    for filename in os.listdir(TEMP_DIR):
                        if filename.startswith(url_hash) and filename.endswith(f'.{ext}'):
                            file_path = os.path.join(TEMP_DIR, filename)
                            return file_path, title, platform, ext
            else:
                for filename in os.listdir(TEMP_DIR):
                    if filename.startswith(url_hash) and filename.endswith(f'.{expected_ext}'):
                        file_path = os.path.join(TEMP_DIR, filename)
                        return file_path, title, platform, expected_ext
            
            for filename in os.listdir(TEMP_DIR):
                if filename.startswith(url_hash):
                    file_path = os.path.join(TEMP_DIR, filename)
                    actual_ext = filename.split('.')[-1] if '.' in filename else format_type
                    return file_path, title, platform, actual_ext
            
            raise FileNotFoundError("Ficheiro descarregado não encontrado")
            
    except Exception as e:
        platform = get_platform_name(url)
        
        error_msg = str(e).lower()
        if 'geo' in error_msg or 'region' in error_msg:
            raise Exception(f"[{platform}] Conteúdo bloqueado na sua região")
        elif 'copyright' in error_msg:
            raise Exception(f"[{platform}] Conteúdo removido por direitos de autor")
        elif 'private' in error_msg:
            raise Exception(f"[{platform}] Conteúdo privado ou indisponível")
        elif 'age' in error_msg:
            raise Exception(f"[{platform}] Conteúdo com restrição de idade")
        elif 'no video' in error_msg or 'audio only' in error_msg:
            raise Exception(f"[{platform}] Conteúdo disponível apenas em áudio")
        else:
            raise Exception(f"[{platform}] Erro no download: {str(e)}")

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'API Multi-Platform Video Downloader Online',
        'version': '2.1',
        'supported_platforms': len(SUPPORTED_PLATFORMS),
        'adult_content_filter': 'Activado',
        'audio_detection': 'Automática',
        'endpoints': {
            '/info': 'POST - Obter informações do vídeo',
            '/download': 'POST - Descarregar vídeo/áudio',
            '/batch-info': 'POST - Informações de múltiplos vídeos',
            '/platforms': 'GET - Listar plataformas suportadas'
        }
    })

@app.route('/platforms', methods=['GET'])
def list_platforms():
    """Lista todas as plataformas suportadas"""
    platforms_grouped = {}
    
    for domain, name in SUPPORTED_PLATFORMS.items():
        if any(x in domain for x in ['youtube', 'vimeo', 'dailymotion']):
            category = 'Vídeo Principal'
        elif any(x in domain for x in ['facebook', 'instagram', 'twitter', 'tiktok']):
            category = 'Redes Sociais'
        elif any(x in domain for x in ['bbc', 'cnn', 'reuters', 'bloomberg']):
            category = 'Notícias'
        elif any(x in domain for x in ['coursera', 'udemy', 'khan', 'mit', 'harvard']):
            category = 'Educação'
        elif any(x in domain for x in ['soundcloud', 'bandcamp', 'mixcloud']):
            category = 'Música/Audio'
        elif any(x in domain for x in ['twitch', 'espn', 'nba']):
            category = 'Streaming/Desporto'
        else:
            category = 'Outras'
        
        if category not in platforms_grouped:
            platforms_grouped[category] = []
        
        platforms_grouped[category].append({
            'domain': domain,
            'name': name
        })
    
    return jsonify({
        'total_platforms': len(SUPPORTED_PLATFORMS),
        'categories': platforms_grouped,
        'adult_content_blocked': len(ADULT_CONTENT_DOMAINS)
    })

@app.route('/info', methods=['POST'])
def get_info():
    """Endpoint para obter informações do vídeo"""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'URL em falta'}), 400
        
        url = data['url'].strip()
        
        is_valid, validation_message = validate_video_url(url)
        if not is_valid:
            return jsonify({'error': validation_message}), 400
        
        cleanup_old_files()
        
        info = get_video_info(url)
        if not info['available']:
            return jsonify({
                'error': f'Conteúdo não disponível: {info.get("error", "Razão desconhecida")}',
                'platform': info.get('platform', 'Desconhecido')
            }), 400
        
        return jsonify({
            'success': True,
            'info': info,
            'validation': validation_message
        })
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@app.route('/download', methods=['POST'])
def download():
    """Endpoint para descarregar vídeo ou áudio"""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'URL em falta'}), 400
        
        url = data['url'].strip()
        format_type = data.get('format', 'mp4').lower()
        quality = data.get('quality', 'medium').lower()
        force_audio = data.get('force_audio', False)
        
        is_valid, validation_message = validate_video_url(url)
        if not is_valid:
            return jsonify({'error': validation_message}), 400
        
        supported_audio_formats = ['mp3', 'aac', 'ogg', 'flac', 'wav']
        supported_video_formats = ['mp4', 'webm', 'avi']
        
        if format_type not in supported_audio_formats + supported_video_formats:
            return jsonify({'error': f'Formato deve ser um de: {", ".join(supported_audio_formats + supported_video_formats)}'}), 400
        
        cleanup_old_files()
        
        file_path, title, platform, actual_ext = download_video(url, format_type, quality, force_audio)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'Ficheiro não encontrado após download'}), 500
        
        safe_title = re.sub(r'[^\w\s-]', '', title).strip()[:50]
        filename = f"{safe_title}.{actual_ext}"
        
        mime_types = {
            'mp3': 'audio/mpeg',
            'aac': 'audio/aac',
            'ogg': 'audio/ogg',
            'flac': 'audio/flac',
            'wav': 'audio/wav',
            'm4a': 'audio/mp4',
            'mp4': 'video/mp4',
            'webm': 'video/webm',
            'avi': 'video/x-msvideo'
        }
        
        mime_type = mime_types.get(actual_ext, 'application/octet-stream')
        
        def remove_file():
            time.sleep(300)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
        
        threading.Thread(target=remove_file, daemon=True).start()
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype=mime_type
        )
        
    except Exception as e:
        return jsonify({'error': f'Erro no download: {str(e)}'}), 500

@app.route('/batch-info', methods=['POST'])
def batch_info():
    """Obter informações de múltiplos vídeos"""
    try:
        data = request.get_json()
        if not data or 'urls' not in data:
            return jsonify({'error': 'Lista de URLs em falta'}), 400
        
        urls = data['urls']
        if not isinstance(urls, list) or len(urls) == 0:
            return jsonify({'error': 'Lista de URLs inválida'}), 400
        
        if len(urls) > 10:
            return jsonify({'error': 'Máximo 10 URLs por vez'}), 400
        
        results = []
        for url in urls:
            url = url.strip()
            
            is_valid, validation_message = validate_video_url(url)
            
            if is_valid:
                info = get_video_info(url)
                results.append({
                    'url': url,
                    'info': info,
                    'validation': validation_message
                })
            else:
                results.append({
                    'url': url,
                    'info': {
                        'available': False, 
                        'error': validation_message,
                        'platform': get_platform_name(url) if not validation_message.startswith('BLOQUEADO') else 'Bloqueado'
                    },
                    'validation': validation_message
                })
        
        return jsonify({
            'success': True,
            'results': results,
            'total_processed': len(results),
            'valid_videos': len([r for r in results if r['info'].get('available', False)]),
            'blocked_adult_content': len([r for r in results if 'BLOQUEADO' in r['validation']])
        })
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

if __name__ == '__main__':
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    try:
        subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
        print("✅ yt-dlp disponível")
    except:
        print("⚠️ AVISO: yt-dlp não encontrado")
    
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ ffmpeg disponível")
    except:
        print("⚠️ AVISO: ffmpeg não encontrado")
    
    print(f"🚀 API iniciada com suporte a {len(SUPPORTED_PLATFORMS)} plataformas")
    print(f"🛡️ Filtro de conteúdo adulto: {len(ADULT_CONTENT_DOMAINS)} domínios bloqueados")
    print(f"🎵 Detecção automática de conteúdo apenas áudio: Activada")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
