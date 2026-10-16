"""Builds Mateen's 16:9 showreel from the website's own reels and posters, cut on the music's beat.

    python build_showreel.py

Inputs: ../assets/site (the web copies the site already uses), the cut points in work/cuts.txt
(ffmpeg scene detection), and "Last Sunrise" from the Hidden Ledger music library (YouTube Audio
Library, attribution not required). Output: showreel.mp4 (1080p) and showreel-web.mp4 (720p).
"""
import os, subprocess, struct

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, 'work')
SITE = os.path.normpath(os.path.join(HERE, '..', 'assets', 'site'))
MUSIC = r'D:\Claude Youtube\HiddenLedger\Music\Last Sunrise - Adam MacDougall.mp3'
W, H, FPS = 1920, 1080, 30
INK, MINT, SAGE = '0x0B2B26', '0xDAF1DE', '0x8EB69B'

BEAT = 0.3593          # measured: 167 bpm
ONE, TWO = 4 * BEAT, 8 * BEAT

# Which reels go where, in order. Dant Al Omran reels lead (the strongest, most edited work).
SINGLES_A = ['dant-al-omran-azizi-55-000-aed-in-just', 'dant-al-omran-samana-barari-heights', 'dant-al-omran-masa-by-imtiaz',
             'dant-al-omran-azizi-venice-the-opportunity', 'dant-al-omran-when-the-wife-gives-you-50-degrees', 'dant-al-omran-why-imtiaz',
             'dant-al-omran-azizi-venice', 'dant-al-omran-binghatti-flare', 'dant-al-omran-emaar', 'dant-al-omran-avana-by-deca']
TRIPTYCHS = [['hampstead-burj-binghatti-jacob-co', 'hampstead-trussardi-residences', 'hampstead-siniya-island-by-sobha'],
             ['hampstead-inside-a-3-bedroom-emaar-apartment', 'hampstead-binghatti-x-mercedes-benz-places', 'hampstead-how-fast-dubai-has-grown'],
             ['hampstead-3-bed-maid-townhouse-tour', 'hampstead-discover-luxury-living', 'hampstead-burj-binghatti-jacob-co']]
POSTERS = ['hampstead-altan-dubai-creek-harbour', 'hampstead-chelsea-residences', 'hampstead-skyvue-sobha-hartland-2', 'hampstead-saria-by-omniyat',
           'hampstead-laya-courtyard', 'hampstead-sidr-residences', 'hampstead-address-residences-dubai-creek-harbour',
           'hampstead-palmiera-3-the-oasis', 'hampstead-binghatti-aquarise', 'freelance-the-cursed-vault']
SINGLES_B = ['hampstead-siniya-island-by-sobha', 'dant-al-omran-masa-by-imtiaz', 'hampstead-inside-a-3-bedroom-emaar-apartment',
             'dant-al-omran-samana-barari-heights', 'hampstead-trussardi-residences', 'dant-al-omran-azizi-venice-the-opportunity']


def run(args):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *args], check=True, cwd=WORK)


def client(key):
    return 'Dant Al Omran' if key.startswith('dant') else 'Freelance' if key.startswith('freelance') else 'Hampstead Homes'


def load_cuts():
    cuts = {}
    for line in open(os.path.join(WORK, 'cuts.txt'), encoding='utf-8'):
        name, dur, times = line.rstrip('\n').split('|')
        cuts[name[:-4]] = (float(dur), [float(t) for t in times.split()])
    return cuts


class Shots:
    """Hands out clean shots from each reel: each starts just after a scene cut and lasts a whole shot
    long enough for the slot, skipping the opening hook and the closing call to action. A reel used twice
    gives a different shot the second time."""
    def __init__(self, cuts):
        self.cuts, self.used = cuts, {}

    def take(self, key, length):
        dur, times = self.cuts[key]
        bounds = [0.0] + times + [dur]
        spans = [(a, b) for a, b in zip(bounds, bounds[1:]) if b - a >= length + 0.3 and a >= 1.0 and b <= dur - 2.0]
        if not spans:  # few cuts: fall back to evenly spaced windows
            spans = [(s, s + length + 0.3) for s in (dur * 0.25, dur * 0.5, dur * 0.7)]
        spans.sort(key=lambda s: -(s[1] - s[0]))      # longest (calmest, clearest) shots first
        n = self.used.get(key, 0)
        self.used[key] = n + 1
        a, b = spans[n % len(spans)]
        return a + 0.15 + max(0.0, (b - a - length - 0.3) / 2)   # centre the window in the shot


def caption(text, size=30):
    path = os.path.join(WORK, 'cap-' + str(abs(hash(text))) + '.txt')
    open(path, 'w', encoding='utf-8').write(text)
    name = os.path.basename(path)
    return (f"drawtext=fontfile=bricolage-400.ttf:textfile={name}:fontsize={size}:fontcolor={MINT}:"
            f"box=1:boxcolor=0x0B2B26@0.72:boxborderw=14:x=48:y=h-th-56")


def card(out, length, lines):
    """A deep green title card; each line fades up in turn."""
    filters = []
    for i, (text, font, size, color, dy) in enumerate(lines):
        path = os.path.join(WORK, f'card-{os.path.basename(out)}-{i}.txt')
        open(path, 'w', encoding='utf-8').write(text)
        t0 = 0.25 + i * 0.22
        # Expressions are quoted: a bare comma inside one ends the option and the rest is read as a new one.
        filters.append(f"drawtext=fontfile={font}:textfile={os.path.basename(path)}:fontsize={size}:fontcolor={color}:"
                       f"x=(w-tw)/2:y='(h-th)/2+({dy})+12*(1-min(1,max(0,(t-{t0})/0.6)))':"
                       f"alpha='min(1,max(0,(t-{t0})/0.6))'")
    run(['-f', 'lavfi', '-i', f'color=c={INK}:s={W}x{H}:r={FPS}:d={length:.3f}', '-vf', ','.join(filters), *ENC, out])


def single(out, key, start, length):
    """A vertical reel full height in the middle, over a blurred, darkened copy of itself."""
    src = os.path.join(SITE, key + '.mp4')
    fc = (f"[0:v]trim=start={start:.3f}:duration={length:.3f},setpts=PTS-STARTPTS,fps={FPS},split[a][b];"
          f"[a]scale={W}:-2,crop={W}:{H},boxblur=40:2,colorchannelmixer=rr=.45:gg=.45:bb=.45[bg];"
          f"[b]scale=-2:{H}[fg];[bg][fg]overlay=(W-w)/2:0,{caption(client(key))}")
    run(['-i', src, '-filter_complex', fc, '-an', *ENC, out])


def triptych(out, keys, starts, length):
    """Three reels side by side on the brand green."""
    pw, ph, gap = 562, 1000, 40
    x0 = (W - 3 * pw - 2 * gap) // 2
    fc = f"color=c={INK}:s={W}x{H}:r={FPS}:d={length:.3f}[base];"
    for i, s in enumerate(starts):
        fc += f"[{i}:v]trim=start={s:.3f}:duration={length:.3f},setpts=PTS-STARTPTS,fps={FPS},scale={pw}:{ph}:force_original_aspect_ratio=increase,crop={pw}:{ph}[p{i}];"
    fc += (f"[base][p0]overlay={x0}:40[t0];[t0][p1]overlay={x0 + pw + gap}:40[t1];[t1][p2]overlay={x0 + 2 * (pw + gap)}:40,"
           f"{caption('Hampstead Homes')}")
    inputs = []
    for k in keys:
        inputs += ['-i', os.path.join(SITE, k + '.mp4')]
    run([*inputs, '-filter_complex', fc, '-an', *ENC, out])


def poster(out, key, length):
    """A still, fitted whole over a blurred copy of itself, pushing in slowly."""
    src = os.path.join(SITE, key + '.jpg')
    fc = (f"[0:v]fps={FPS},split[a][b];"
          f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:2,colorchannelmixer=rr=.5:gg=.5:bb=.5[bg];"
          f"[b]scale=1560:880:force_original_aspect_ratio=decrease,"
          f"scale=w='trunc(iw*(1+0.05*t/{length:.3f})/2)*2':h=-2:eval=frame[fg];"
          f"[bg][fg]overlay=(W-w)/2:(H-h)/2,{caption(client(key))}")
    run(['-loop', '1', '-t', f'{length:.3f}', '-i', src, '-filter_complex', fc, *ENC, out])


ENC = ['-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', str(FPS)]


def main():
    cuts, shots, parts = load_cuts(), None, []
    shots = Shots(cuts)
    seg = lambda n: os.path.join(WORK, f'seg{n:02d}.mp4')
    n = 0

    def add(fn, *a):
        nonlocal n
        fn(seg(n), *a); parts.append(seg(n)); n += 1
        print('  segment', n, flush=True)

    add(card, TWO, [('Mateen Ahsan', 'bricolage-600.ttf', 128, MINT, -50),
                    ('Graphic Designer & Video Editor  ·  Riyadh', 'bricolage-400.ttf', 46, SAGE, 70)])
    for k in SINGLES_A:
        add(single, k, shots.take(k, ONE), ONE)
    for keys in TRIPTYCHS:
        add(triptych, keys, [shots.take(k, TWO) for k in keys], TWO)
    for k in POSTERS:
        add(poster, k, ONE)
    for k in SINGLES_B:
        add(single, k, shots.take(k, ONE), ONE)
    add(card, 3 * ONE, [("Let's make something together.", 'bricolage-600.ttf', 86, MINT, -70),
                        ('mateen.saud@gmail.com', 'bricolage-400.ttf', 52, MINT, 40),
                        ('Riyadh  ·  Available now', 'bricolage-400.ttf', 38, SAGE, 120)])

    with open(os.path.join(WORK, 'parts.txt'), 'w') as f:
        f.writelines(f"file '{os.path.basename(p)}'\n" for p in parts)
    run(['-f', 'concat', '-safe', '0', '-i', 'parts.txt', '-c', 'copy', 'video.mp4'])
    total = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0',
                                  os.path.join(WORK, 'video.mp4')], capture_output=True, text=True).stdout)
    out = os.path.join(HERE, 'showreel.mp4')
    run(['-i', 'video.mp4', '-i', MUSIC, '-filter_complex',
         f"[1:a]atrim=0:{total:.3f},afade=t=in:d=0.3,afade=t=out:st={total - 2.2:.3f}:d=2.2,loudnorm=I=-14:TP=-1.5:LRA=11[a]",
         '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out])
    run(['-i', out, '-vf', 'scale=1280:-2', '-c:v', 'libx264', '-preset', 'medium', '-crf', '24', '-c:a', 'copy',
         '-movflags', '+faststart', os.path.join(HERE, 'showreel-web.mp4')])
    print(f'done: {total:.1f}s, {len(parts)} segments')


if __name__ == '__main__':
    main()
