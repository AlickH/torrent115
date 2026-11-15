#!/usr/bin/env python3
"""内置 BT 下载器：基于 libtorrent 的极简下载管理。"""
import os
import threading
import time

import libtorrent as lt

_lock = threading.RLock()
_session = None
_handles = {}


def _get_session():
    global _session
    cfg = {}
    port = 6881
    with _lock:
        if _session is None:
            settings = {
                "listen_interfaces": f"0.0.0.0:{port},[::]:{port}",
                "enable_dht": True,
                "enable_lsd": True,
                "enable_upnp": True,
                "enable_natpmp": True,
                "alert_mask": lt.alert.category_t.error_notification | lt.alert.category_t.status_notification,
                "connections_limit": 500,
                "connection_speed": 200,
                "peer_connect_timeout": 5,
                "request_timeout": 10,
                "max_failcount": 3,
                "announce_to_all_trackers": True,
                "announce_to_all_tiers": True,
                "prefer_udp_trackers": True,
                "in_encryption": "1",
                "out_encryption": "1",
                "allow_multiple_connections_per_ip": True,
                "aio_threads": 8,
                "hashing_threads": 2,
                "utp_connect_timeout": 5,
                "download_rate_limit": 0,
                "upload_rate_limit": 0,
                "dht_bootstrap_nodes": "router.bittorrent.com:6881,dht.transmissionbt.com:6881,router.utorrent.com:6881,dht.libtorrent.org:25401",
            }
            _session = lt.session(settings)
            _session.start_dht()
            _session.start_lsd()
            _session.start_upnp()
            _session.start_natpmp()
        return _session


def _save_path(cfg):
    path = (cfg.get("local_save_path") or "/data/downloads").strip() or "/data/downloads"
    os.makedirs(path, exist_ok=True)
    return path


def add_magnet(cfg, magnet):
    s = _get_session()
    params = lt.parse_magnet_uri(magnet)
    params.save_path = _save_path(cfg)
    h = s.add_torrent(params)
    with _lock:
        _handles[str(h.info_hash())] = h
    return str(h.info_hash())


def _state_name(h):
    st = h.status()
    if h.is_valid():
        pass
    if st.paused:
        return "paused"
    if st.state == lt.torrent_status.seeding:
        return "seeding"
    if st.state == lt.torrent_status.finished:
        return "finished"
    if st.state == lt.torrent_status.downloading:
        return "downloading"
    if st.state == lt.torrent_status.checking_files:
        return "checking"
    return "queued"


def tasks():
    s = _get_session()
    out = []
    with _lock:
        current = {}
        for h in s.get_torrents():
            hh = str(h.info_hash())
            current[hh] = h
            _handles.setdefault(hh, h)
        _handles.update(current)
    for hh, h in list(_handles.items()):
        try:
            st = h.status()
            if not st.has_metadata:
                name = st.name or hh[:12]
                out.append({"hash": hh, "name": name, "progress": 0, "state": "metadata",
                            "download_rate": 0, "upload_rate": 0, "total": 0, "done": 0,
                            "seeders": 0, "peers": 0, "save_path": st.save_path})
                continue
            out.append({
                "hash": hh,
                "name": st.name,
                "progress": round(float(st.progress) * 100, 1),
                "state": _state_name(h),
                "download_rate": int(st.download_rate),
                "upload_rate": int(st.upload_rate),
                "total": int(st.total_wanted),
                "done": int(st.total_wanted_done),
                "seeders": int(st.num_seeds),
                "peers": int(st.num_peers),
                "save_path": st.save_path,
            })
        except Exception:
            continue
    return out


def pause(hash_):
    with _lock:
        h = _handles.get(hash_)
    if h:
        h.pause()
        return True
    return False


def resume(hash_):
    with _lock:
        h = _handles.get(hash_)
    if h:
        h.resume()
        return True
    return False


def delete(hash_, delete_files=False):
    with _lock:
        h = _handles.pop(hash_, None)
    if not h:
        return False
    s = _get_session()
    if delete_files:
        s.remove_torrent(h, lt.options_t.delete_files)
    else:
        s.remove_torrent(h)
    return True
