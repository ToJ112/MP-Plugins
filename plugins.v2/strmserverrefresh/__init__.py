import time
from pathlib import Path
from typing import Any, List, Dict, Tuple, Optional

from app.core.context import MediaInfo
from app.core.event import eventmanager, Event
from app.helper.mediaserver import MediaServerHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import TransferInfo, RefreshMediaItem, ServiceInfo
from app.schemas.types import EventType


class StrmServerRefresh(_PluginBase):
    # 插件名称
    plugin_name = "转移后strm落文件并刷新库"
    # 插件描述
    plugin_desc = "入库后自动生成strm并更新Emby/Jellyfin/Plex服务器海报墙。"
    # 插件图标
    plugin_icon = "refresh.png"
    # 插件版本
    plugin_version = "0.0.1"
    # 插件作者
    plugin_author = "jtning"
    # 作者主页
    author_url = "https://github.com/TOJ112"
    # 插件配置项ID前缀
    plugin_config_prefix = "strmserverrefresh_"
    # 加载顺序
    plugin_order = 99
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    mediaserver_helper = None
    _enabled = False
    _delay = 0
    _mediaservers = None

    def init_plugin(self, config: dict = None):
        self.mediaserver_helper = MediaServerHelper()
        if config:
            self._enabled = config.get("enabled")
            self._delay = config.get("delay") or 0
            self._mediaservers = config.get("mediaservers") or []
            self._strmpath = config.get("strm_path")
            self._alistpath = config.get("alist_path")

    @property
    def service_infos(self) -> Optional[Dict[str, ServiceInfo]]:
        """
        服务信息
        """
        if not self._mediaservers:
            logger.warning("尚未配置媒体服务器，请检查配置")
            return None

        services = self.mediaserver_helper.get_services(name_filters=self._mediaservers)
        if not services:
            logger.warning("获取媒体服务器实例失败，请检查配置")
            return None

        active_services = {}
        for service_name, service_info in services.items():
            if service_info.instance.is_inactive():
                logger.warning(f"媒体服务器 {service_name} 未连接，请检查配置")
            else:
                active_services[service_name] = service_info

        if not active_services:
            logger.warning("没有已连接的媒体服务器，请检查配置")
            return None

        return active_services

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'multiple': True,
                                            'chips': True,
                                            'clearable': True,
                                            'model': 'mediaservers',
                                            'label': '媒体服务器',
                                            'items': [{"title": config.name, "value": config.name}
                                                      for config in self.mediaserver_helper.get_configs().values()]
                                        }
                                    }, {
                                        'component': 'VCol',
                                        'props': {
                                            'cols': 12,
                                        },
                                        'content': [
                                            {
                                                'component': 'VTextField',
                                                'props': {
                                                    'model': 'delay',
                                                    'label': '延迟时间（秒）',
                                                    'placeholder': '0'
                                                }
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'strm_path',
                                            'label': 'strm目标地址',
                                            'placeholder': '/LINK'
                                        }
                                    }
                                ]
                            }, {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'alist_path',
                                            'label': 'alist替换地址',
                                            'placeholder': 'http://xx.xx:5244/d/115'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "delay": 0
        }

    def get_page(self) -> List[dict]:
        pass

    @eventmanager.register(EventType.TransferComplete)
    def refresh(self, event: Event):
        """
        发送通知消息
        """
        if not self._enabled:
            return

        event_info: dict = event.event_data
        if not event_info:
            return

        # 刷新媒体库
        if not self.service_infos:
            return

        # 入库数据
        transferinfo: TransferInfo = event_info.get("transferinfo")
        if not transferinfo or not transferinfo.target_diritem or not transferinfo.target_diritem.path:
            return

        if self._strmpath:
            strm_content = self.__format_content(file_path=str(transferinfo.file_list_new))
            self.__gen_strm()
            # 生成strm文件
            # self.__create_strm_file(strm_file=target_file,
            #                         strm_content=strm_content)
        if self._delay:
            logger.info(f"延迟 {self._delay} 秒后刷新媒体库... ")
            time.sleep(float(self._delay))

        mediainfo: MediaInfo = event_info.get("mediainfo")

        items = [
            RefreshMediaItem(
                title=mediainfo.title,
                year=mediainfo.year,
                type=mediainfo.type,
                category=mediainfo.category,
                target_path=Path(transferinfo.target_diritem.path)
            )
        ]

        for name, service in self.service_infos.items():
            # Emby
            if self.mediaserver_helper.is_media_server("emby", service=service):
                service.instance.refresh_library_by_items(items)

            # Jeyllyfin
            if self.mediaserver_helper.is_media_server("jellyfin", service=service):
                # FIXME Jellyfin未找到刷新单个项目的API
                service.instance.refresh_root_library()

            # Plex
            if self.mediaserver_helper.is_media_server("plex", service=service):
                service.instance.refresh_library_by_items(items)

    def stop_service(self):
        """
        退出插件
        """
        pass

    def __format_content(self, file_path):
        logger.error(f"当前filepath: {file_path}")
        pass

    def __gen_strm(self):
        logger.error(f"读取到的")
        pass
