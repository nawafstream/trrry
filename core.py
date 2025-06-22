# -*- coding: utf-8 -*-
import sys, os, time, json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import xbmc, xbmcaddon, xbmcgui, xbmcplugin

# --- Globals specific to this file ---
_ADDON = xbmcaddon.Addon()
_ADDON_ID = _ADDON.getAddonInfo('id')
_ADDON_NAME = _ADDON.getAddonInfo('name')
_ADDON_HANDLE = int(sys.argv[1])
_BASE_URL = f"plugin://{_ADDON_ID}"

def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[{_ADDON_ID}] {msg}", level=level)

def notify(msg):
    xbmcgui.Dialog().notification(_ADDON_NAME, msg)

def make_request(url, data=None, headers=None, is_json=True):
    if headers is None: headers = {}
    if data:
        encoded_data = urlencode(data).encode('utf-8')
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        req = Request(url, data=encoded_data, headers=headers)
    else:
        req = Request(url, headers=headers)
    
    try:
        with urlopen(req, timeout=30) as response:
            response_body = response.read().decode('utf-8')
            return json.loads(response_body) if is_json else response_body
    except HTTPError as e:
        error_body = e.read().decode('utf-8', 'ignore')
        log(f"HTTP Error: {e.code} - {e.reason}. Body: {error_body}", level=xbmc.LOGERROR)
        xbmcgui.Dialog().ok(_ADDON_NAME, f"HTTP Error: {e.code}\n{error_body}")
        return None
    except Exception as e:
        import traceback
        log(f"Generic Request Error: {traceback.format_exc()}", level=xbmc.LOGERROR)
        xbmcgui.Dialog().ok(_ADDON_NAME, f"A network error occurred: {e}")
        return None

# ===================================================================================================
# SECTION: Google Drive API Client
# ===================================================================================================
class GoogleDrive:
    def __init__(self):
        # ==================== بياناتك الجديدة والصحيحة هنا ====================
        self.client_id = "245321815916-h1b55dt7gi6t6o9rjo4udhvlt4na7oiu.apps.googleusercontent.com"
        self.client_secret = "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"
        # ===================================================================
        
        self.device_code_url = "https://oauth2.googleapis.com/device/code"
        self.token_url = "https://oauth2.googleapis.com/token"
        self.api_url = "https://www.googleapis.com/drive/v3"
        
        # الصلاحيات الكاملة التي يجب أن تتطابق مع إعدادات جوجل
        self.scope = "openid email profile https://www.googleapis.com/auth/drive.readonly"
        
        self._load_tokens()

    def _load_tokens(self):
        self.access_token = _ADDON.getSetting('gdrive.access_token')
        self.refresh_token = _ADDON.getSetting('gdrive.refresh_token')
        try: self.expires_at = float(_ADDON.getSetting('gdrive.expires_at'))
        except: self.expires_at = 0

    def _save_tokens(self, data):
        self.access_token = data['access_token']
        if 'refresh_token' in data:
            self.refresh_token = data['refresh_token']
            _ADDON.setSetting('gdrive.refresh_token', self.refresh_token)
        self.expires_at = time.time() + int(data['expires_in'])
        _ADDON.setSetting('gdrive.access_token', self.access_token)
        _ADDON.setSetting('gdrive.expires_at', str(self.expires_at))
        log("Tokens saved successfully.")

    def _refresh_token_logic(self):
        if not self.refresh_token: return False
        log("Access token expired. Refreshing...")
        payload = {'client_id': self.client_id, 'client_secret': self.client_secret, 'refresh_token': self.refresh_token, 'grant_type': 'refresh_token'}
        token_data = make_request(self.token_url, data=payload)
        if token_data and 'access_token' in token_data:
            self._save_tokens(token_data)
            log("Token refreshed successfully.")
            return True
        log("Failed to refresh token.", level=xbmc.LOGERROR)
        return False

    def is_authorized(self): return bool(self.refresh_token)

    def _get_auth_header(self):
        if self.expires_at > 0 and time.time() + 60 > self.expires_at:
            if not self._refresh_token_logic(): return None
        return {'Authorization': f'Bearer {self.access_token}'}

    def list_files(self, folder_id):
        headers = self._get_auth_header()
        if not headers: return []
        params = {'q': f"'{folder_id}' in parents and trashed = false", 'orderBy': 'folder,name',
                  'fields': 'files(id, name, mimeType, iconLink, thumbnailLink)', 'pageSize': 1000,
                  'supportsAllDrives': 'true', 'includeItemsFromAllDrives': 'true'}
        url = f"{self.api_url}/files?{urlencode(params)}"
        response = make_request(url, headers=headers)
        return response.get('files', []) if response else []

    def auth(self):
        payload = {'client_id': self.client_id, 'scope': self.scope}
        device_code_data = make_request(self.device_code_url, data=payload)
        if not device_code_data:
            notify("Could not contact Google to start auth.")
            return

        user_code = device_code_data['user_code']
        verification_url = device_code_data['verification_url']
        device_code = device_code_data['device_code']
        interval = int(device_code_data['interval'])
        expires_in = int(device_code_data['expires_in'])

        dialog_text = f"1. Go to [B]{verification_url}[/B] on another device.\n2. Enter the code: [B]{user_code}[/B]\nThis code will expire in {expires_in // 60} minutes."
        progress_dialog = xbmcgui.DialogProgress()
        progress_dialog.create(_ADDON_NAME, dialog_text)
        
        start_time = time.time()
        while time.time() - start_time < expires_in:
            if progress_dialog.iscanceled():
                progress_dialog.close()
                return
            progress = int(((time.time() - start_time) / expires_in) * 100)
            progress_dialog.update(progress)
            time.sleep(interval)
            
            payload = {'client_id': self.client_id, 'client_secret': self.client_secret, 
                       'device_code': device_code, 'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'}
            token_data = make_request(self.token_url, data=payload)

            if token_data and 'access_token' in token_data:
                self._save_tokens(token_data)
                progress_dialog.close()
                notify("Authorization successful!")
                xbmc.executebuiltin('Container.Refresh')
                return
        
        progress_dialog.close()
        notify("Authorization failed or timed out.")

def add_dir(name, action, is_folder=True, list_item=None, **kwargs):
    if list_item is None: list_item = xbmcgui.ListItem(name)
    kwargs['action'] = action
    url = f"{_BASE_URL}?{urlencode(kwargs)}"
    xbmcplugin.addDirectoryItem(handle=_ADDON_HANDLE, url=url, listitem=list_item, isFolder=is_folder)

def main_menu():
    gdrive = GoogleDrive()
    if not gdrive.is_authorized():
        add_dir("Authorize Google Drive", 'auth_gdrive', is_folder=False)
    else:
        add_dir("My Drive", 'browse_gdrive', folder_id='root')
    add_dir("Settings", 'settings', is_folder=False)
    xbmcplugin.endOfDirectory(_ADDON_HANDLE)

def browse_gdrive(folder_id):
    gdrive = GoogleDrive()
    files = gdrive.list_files(folder_id or 'root')
    xbmcplugin.setContent(_ADDON_HANDLE, 'videos')
    for item in files:
        is_folder = item['mimeType'] == 'application/vnd.google-apps.folder'
        is_playable = 'video/' in item['mimeType'] or 'image/' in item['mimeType']
        
        li = xbmcgui.ListItem(item['name'])
        li.setInfo('video', {'title': item['name'], 'plot': item['mimeType']})
        art = {'icon': item.get('iconLink'), 'thumb': item.get('thumbnailLink')}
        li.setArt(art)
        
        if is_folder:
            add_dir(item['name'], 'browse_gdrive', folder_id=item['id'], list_item=li)
        elif is_playable:
            li.setProperty('IsPlayable', 'true')
            add_dir(item['name'], 'play_gdrive', is_folder=False, list_item=li, file_id=item['id'])
            
    xbmcplugin.endOfDirectory(_ADDON_HANDLE)

def play_gdrive(file_id):
    gdrive = GoogleDrive()
    if not gdrive._get_auth_header():
        notify("Could not authorize. Please try again.")
        xbmcplugin.setResolvedUrl(_ADDON_HANDLE, False, xbmcgui.ListItem())
        return

    link = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
    play_item = xbmcgui.ListItem(path=f"{link}|Authorization=Bearer {gdrive.access_token}")
    xbmcplugin.setResolvedUrl(_ADDON_HANDLE, True, listitem=play_item)

def auth_gdrive():
    GoogleDrive().auth()

def open_settings():
    _ADDON.openSettings()
