"""Builds the website's work from the owner's folder, which is the single source of truth.

    python build-content.py

Reads  C:\\Users\\FRONTIER LABS\\Desktop\\Portfolio\\On the website\\{Real estate,Video,Social,Photo and CV}
Writes assets/site/  (web-sized copies)  and  assets/site/items.js  (the ordered work list the page reads).

File names carry everything the page shows: "NN Client - Title (type).ext". NN sets the order within a
folder; the folders are then interleaved so the first screen of work mixes posters, reels and posts.
A web copy is only rebuilt when its original is newer, so a rebuild after deleting a file takes seconds.
"""
import json, os, re, shutil, subprocess

SRC = r'C:\Users\FRONTIER LABS\Desktop\Portfolio\On the website'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'assets', 'site')

FOLDERS = [('Real estate', 'print'), ('Video', 'video'), ('Social', 'social')]
CLIENTS = {'Hampstead': 'Hampstead Homes'}
DEFAULT_TYPE = {'print': 'Poster', 'video': 'Reel', 'social': 'Social post'}
NAME = re.compile(r'^\d+\s+(?P<client>.+?)\s+-\s+(?P<title>.+?)(?:\s+\((?P<kind>[^)]+)\))?$')


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def stale(src, dst):
    return not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(src)


def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *args], check=True)


def build_folder(folder, f):
    path = os.path.join(SRC, folder)
    if not os.path.isdir(path):
        return []
    items = []
    for name in sorted(os.listdir(path)):
        stem, ext = os.path.splitext(name)
        m = NAME.match(stem)
        if not m:
            print(f'  skipped (name not "NN Client - Title"): {folder}\\{name}')
            continue
        client = CLIENTS.get(m['client'], m['client'])
        kind = m['kind']
        label = (kind[0].upper() + kind[1:]) if kind else DEFAULT_TYPE[f]
        if kind == 'escape room':
            label = 'Escape room poster'
        key = slug(f"{m['client']} {m['title']}")
        src = os.path.join(path, name)
        if f == 'video':
            dst, poster = os.path.join(OUT, key + '.mp4'), os.path.join(OUT, key + '.jpg')
            if stale(src, dst):
                print(f'  converting {name}')
                ffmpeg('-threads', '2', '-i', src, '-vf', "scale='min(720,iw)':-2,fps=30", '-c:v', 'libx264', '-preset', 'medium',
                       '-crf', '25', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-c:a', 'aac', '-b:a', '96k', dst)
                ffmpeg('-ss', '3', '-i', dst, '-frames:v', '1', '-q:v', '4', poster)
            items.append({'f': f, 'vid': f'assets/site/{key}.mp4', 'poster': f'assets/site/{key}.jpg',
                          't': m['title'], 'c': f'{client} · {label}'})
        else:
            dst = os.path.join(OUT, key + '.jpg')
            if stale(src, dst):
                print(f'  resizing {name}')
                ffmpeg('-i', src, '-vf', "scale='min(1800,iw)':-2", '-q:v', '3', dst)
            items.append({'f': f, 'img': f'assets/site/{key}.jpg', 't': m['title'], 'c': f'{client} · {label}'})
    return items


def main():
    os.makedirs(OUT, exist_ok=True)
    groups = [build_folder(folder, f) for folder, f in FOLDERS]
    # Interleave the folders so posters, reels and posts alternate down the grid.
    ordered = []
    for i in range(max(map(len, groups), default=0)):
        for g in groups:
            if i < len(g):
                ordered.append(g[i])

    # The showreel: the first video in the Showreel folder becomes the featured reel above the work.
    showreel = None
    sr = os.path.join(SRC, 'Showreel')
    if os.path.isdir(sr):
        reels = sorted(n for n in os.listdir(sr) if n.lower().endswith('.mp4'))
        if reels:
            src, dst, poster = os.path.join(sr, reels[0]), os.path.join(OUT, 'showreel.mp4'), os.path.join(OUT, 'showreel.jpg')
            if stale(src, dst):
                print(f'  converting {reels[0]}')
                ffmpeg('-i', src, '-vf', "scale='min(1280,iw)':-2", '-c:v', 'libx264', '-preset', 'medium', '-crf', '24',
                       '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-c:a', 'aac', '-b:a', '160k', dst)
                ffmpeg('-ss', '1.8', '-i', dst, '-frames:v', '1', '-q:v', '3', poster)
            showreel = {'vid': 'assets/site/showreel.mp4', 'poster': 'assets/site/showreel.jpg'}

    pc = os.path.join(SRC, 'Photo and CV')
    if os.path.isdir(pc):
        for name in os.listdir(pc):
            src = os.path.join(pc, name)
            if 'photo' in name.lower() and stale(src, os.path.join(HERE, 'assets', 'me.jpg')):
                ffmpeg('-i', src, '-q:v', '3', os.path.join(HERE, 'assets', 'me.jpg'))
            if name.lower().endswith('.pdf'):
                os.makedirs(os.path.join(HERE, 'assets', 'cv'), exist_ok=True)
                shutil.copy2(src, os.path.join(HERE, 'assets', 'cv', 'Mateen_Ahsan_Design_CV.pdf'))

    # Remove web copies whose original was deleted from the folder.
    keep = {os.path.basename(v) for it in ordered + ([showreel] if showreel else [])
            for v in (it.get('img'), it.get('vid'), it.get('poster')) if v}
    for name in os.listdir(OUT):
        if name not in keep and name != 'items.js':
            os.remove(os.path.join(OUT, name))
            print(f'  removed {name}')

    with open(os.path.join(OUT, 'items.js'), 'w', encoding='utf-8') as fh:
        fh.write('// Generated by build-content.py from the "On the website" folder. Do not edit by hand.\n')
        fh.write('window.SITE_ITEMS = ' + json.dumps(ordered, ensure_ascii=False, indent=1) + ';\n')
        fh.write('window.SITE_SHOWREEL = ' + json.dumps(showreel) + ';\n')
    # Stamp the page's link to items.js with a new version, so browsers fetch the fresh list instead of a cached one.
    page = os.path.join(HERE, 'index.html')
    if os.path.exists(page):
        html = open(page, encoding='utf-8').read()
        stamp = str(int(os.path.getmtime(os.path.join(OUT, 'items.js'))))
        html = re.sub(r'assets/site/items\.js(\?v=\d+)?', f'assets/site/items.js?v={stamp}', html)
        open(page, 'w', encoding='utf-8').write(html)
    counts = {f: sum(1 for it in ordered if it['f'] == f) for _, f in FOLDERS}
    print(f'{len(ordered)} pieces: {counts}')


if __name__ == '__main__':
    main()
