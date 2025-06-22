# -*- coding: utf-8 -*-
import sys
from urllib.parse import parse_qsl

_ARGS = dict(parse_qsl(sys.argv[2][1:]))
action = _ARGS.get('action')

if action is None:
    from lib.core import main_menu
    main_menu()
elif action == 'auth_gdrive':
    from lib.core import auth_gdrive
    auth_gdrive()
elif action == 'browse_gdrive':
    from lib.core import browse_gdrive
    browse_gdrive(_ARGS.get('folder_id'))
elif action == 'play_gdrive':
    from lib.core import play_gdrive
    play_gdrive(_ARGS.get('file_id'))
elif action == 'settings':
    from lib.core import open_settings
    open_settings()
