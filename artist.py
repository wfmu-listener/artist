#!/usr/bin/env python
import requests
import time
from bs4 import BeautifulSoup as bs
import sqlite3

base = 'https://www.wfmu.org'
db = sqlite3.connect('/home/cgw/Hack/AOTW/shows.sqlite')

def create_shows_table():
    cur = db.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS shows(date, show_num)""")
    for year in range(2017, 2024):
        rep = requests.get(base + '/playlists/WA%s' % year)
        s = bs(rep.content, 'html.parser')
        div = s.find('div', class_='showlist')
        for li in reversed(div.find_all('li')):
            date = li.text.strip().split(':')[0]
            td = time.strptime(date, '%B %d, %Y')
            date = time.strftime('%Y-%m-%d', td)
            url = li.find_all('a', href=True)[1]['href'] # skip ★
            show_num = url.split('/')[-1]
            print(date, show_num)
            cur.execute("""INSERT INTO shows VALUES("%s",%s)""" %
                        (date, show_num))
    db.commit()


def create_archive_table():
    cur = db.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS archive(show_num, archive, UNIQUE(show_num))""")
    res = cur.execute("""SELECT show_num FROM shows""")
    for r in res.fetchall():
        show_num = r[0]
        url = '/playlists/shows/%s' % show_num
        rep = requests.get(base + url)
        s = bs(rep.content, 'html.parser')
        tab = s.find(id='drop_table')
        for a in tab.find_all('a', href=True):
            href = a['href']
            if 'flashplayer' in href:
                tok = href.split('&')
                archive = tok[2].split('=')[1]
                sql = """INSERT INTO archive VALUES (%s,%s)""" % (show_num, archive)
                print(sql)
                cur.execute(sql)
                break
    db.commit()

def make_play_link(show_num, start_time):
    cur = db.cursor()
    res = cur.execute("""SELECT archive FROM archive WHERE show_num=%s"""%show_num)
    r = res.fetchone()
    if not r:
        return
    archive = r[0]
    return(base + "/flashplayer.php?version=3&show=%s&archive=%s&starttime=%s" % (
        show_num, archive, start_time))


def create_tracks_table():
    cur = db.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS tracks(show_num,artist,title,comment,time)""")

    res = cur.execute("""SELECT show_num FROM shows ORDER BY show_num""")
    for show_num in res.fetchall():
        show_num = show_num[0]
        print(show_num)
        res = cur.execute("""SELECT * FROM tracks WHERE show_num=%s""" % show_num)
        if res.fetchone():
            continue
        url = '/playlists/shows/%s' % show_num
        rep = requests.get(base + url)
        s = bs(rep.content, 'html.parser')
        tab = s.find(id='drop_table')
        for row in tab.find_all('tr'):
            def get(name):
                x = row.find('td', class_='col_'+name)
                return x.text.strip().replace('"','""') if x else ''
            comment = get('comments')
            artist = get('artist')
            title = get('song_title')
            if title:
                title = title.split('→')[0].strip()
            time = get('live_timestamps_flag')
            if time:
                time = time.split()[0].strip()
            print(comment, artist, title, comment, time)
            sql = ("""INSERT INTO tracks VALUES (%s,"%s","%s","%s","%s")""" %
                   (show_num,artist,title,comment,time))
            print(sql)
            cur.execute(sql)


    db.commit()


def find_aotw():
    cur = db.cursor()
    res = cur.execute("""SELECT * FROM shows ORDER BY date""")
    monday = None
    shows = []
    def do_week():
        #print("Shows:", shows)
        sql = ("""SELECT DISTINCT artist FROM tracks
        WHERE show_num IN (%s)
        AND comment LIKE '%%artist of the week%%'""" %
               str(shows)[1:-1])
        res = cur.execute(sql)
        artists = res.fetchall()
        if artists:
            artists = [a[0].strip() for a in artists]
            return artists

        sql = ("""SELECT DISTINCT TITLE FROM tracks
        WHERE show_num IN (%s)
        AND title LIKE '%%artist of the week%%'""" %
               str(shows)[1:-1])
        res = cur.execute(sql)
        titles = res.fetchall()
        if titles:
            titles = [t[0].split(':')[-1].strip() for t in titles]
            return titles

        # Look for any artist played all 5 days
        alist = []
        for show in shows:
            sql = """SELECT DISTINCT artist FROM tracks WHERE show_num = %s""" % show
            res = cur.execute(sql)
            alist.append(set(r[0] for r in res.fetchall()))
        res, alist = alist[0], alist[1:]
        while alist:
            res.intersection_update(alist[0])
            alist = alist[1:]
        for x in '', 'Music behind DJ:':
            if x in res:
                res.remove(x)
        return list(res)


    for (date, show_num) in res.fetchall():
        if date < '2018-12-03':
            continue
        td = time.strptime(date, '%Y-%m-%d')
        if td.tm_wday == 0:
            if shows:
                res = cur.execute("""SELECT * FROM aotw WHERE week='%s'"""%
                                  monday)
                r= res.fetchall()
                if r:
                    monday = date
                    shows = []
                    print(r)
                    continue
                res = do_week()
                if len(res) == 1:
                    cur.execute("""INSERT INTO aotw VALUES("%s", "%s")""" %
                                (monday, res[0]))
                elif len(res) > 1:
                    for i,r in enumerate(res):
                        print(i, r)
                    x = input("? ")
                    try:
                        x = int(x)
                        cur.execute("""INSERT INTO aotw VALUES("%s", "%s")""" %
                                    (monday, res[x]))
                    except ValueError:
                        pass
                else:
                    res = input("? ")
                    if res:
                        cur.execute("""INSERT INTO aotw VALUES("%s", "%s")""" %
                                    (monday, res))

            monday = date
            shows = []
        shows.append(show_num)
        db.commit()

    if shows:
        res = do_week()
        cur.execute("""INSERT INTO aotw VALUES("%s", "%s")""" %
                    (monday, res[0]))

    db.commit()


def find_tracks(artist, show_num):
    cur = db.cursor()
    lower = artist.lower()
    if lower.startswith("the"):
        artist = artist[4:].strip()
        lower = artist.lower()
    candidates = [artist]
    if 'hall' in lower and 'oates' in lower:
        candidates = ['Hall and Oates',
                      'Hall & Oates',
                      'Daryl Hall and John Oates',
                      'Daryl Hall & John Oates']

    if 'public' in lower and 'image' in lower:
        candidates = ['PIL',
                      'P.I.L',
                      'Public Image Ltd.']
    if 'mazzy' in lower:
        candidates = ['mazzy star',
                      'hope sandoval']
    if '52' in lower:
        candidates = ['B-52s', 'B52s', "B52's", "B-52's", "B 52s", "B 52's"];
    if 'television' in lower or 'verlaine' in lower:
        candidates = ['tom verlaine', 'television']
    if 'elevators' in lower:
        candidates = ['elevators', 'erickson', 'erikson']
    if 'zappa' in lower:
        candidates = ['zappa', 'mothers of invention']
    if 'hosono' in lower:
        candidates = ['hosono', 'hosno', 'yellow magic']
    if 'richman' in lower:
        candidates = ['richman', 'modern lovers']
    if 'johansen' in lower:
        candidates = ['new york dolls', 'david johansen']
    if 'kool' in lower and 'gang' in lower:
        candidates = ['kool and the gang', 'kool & the gang']
    if 'galaxie' in lower:
        candidates = ['galaxy 500', 'galaxie 500']
    if 'scratch' in lower:
        candidates = ['scratch', 'perry']
    if 'turner' in lower and 'tina' in lower:
        candidates = ['tina turner', 'ike and tina turner', 'ike & tina turner']
    if lower == 'dbs':
        candidates = ['dbs', "db's", "db’s"]
    if 'tribe' in lower and 'quest' in lower:
        candidates = ['tribe called quest']
    if artist == 'Françoise Hardy':
        candidates = ['Françoise Hardy', 'Francoise Hardy']
    if artist == 'T. Rex':
        candidates = ['T-Rex', 'T Rex', 'T. Rex']
    if 'gladys knight' in lower:
        candidates = ['gladys knight']
    if 'bee gee' in lower:
        candidates = ['bee gees', 'beegees']
    if 'hatfield' in lower:
        candidates = ['hatfield', 'blake babies']
    if 'riperton' in lower:
        candidates = ['ripperton', 'riperton']
    if 'clatyon' in lower:  # merry/mary
        candidates = ['clatyon']
    if 'lee fields' in lower:
        candidates = ['lee fields']
    if 'harvey' in lower: #PJ, P.J, P J
        candidates = ['harvey']
    if 'björk' in lower:
        candidates = ['björk', 'sugarcubes']
    if 'ronettes' in lower:
        candidates = ['ronettes', 'ronnettes']
    for c in candidates:
        res = cur.execute("""SELECT * FROM tracks WHERE artist like '%%%s%%'
        AND show_num = %s""" %
                          (c.replace("'", "''"), show_num))

        r = res.fetchall()
        if r:
            return r[0]
    # Sometimes title and artist are swapped
    for c in candidates:
        res = cur.execute("""SELECT * FROM tracks WHERE title like '%%%s%%'
        AND show_num = %s""" %
                          (c.replace("'", "''"), show_num))

        r = res.fetchall()
        if r:
            r = r[0]
            return (r[0], r[2], r[1], r[3], r[4])





def find_aotw_plays():
    print("""<html>
  <head>
    <title>Wake and Bake Featured Artist of the Week Index
    </title>
  </head>""")
    print("""  <body>""")
    print("""    <table border=1>""")

    cur = db.cursor()
    res = cur.execute("""SELECT week FROM aotw ORDER BY week""")
    weeks = [r[0] for r in res.fetchall()]
    for week in weeks:
        res = cur.execute("""SELECT artist FROM aotw WHERE week='%s'""" %
                          week)
        artist = res.fetchone()[0]

        print("""      <tr>""")
        print("""        <td align="center" colspan=3>""")
        print("""          <font size=+1>""")
        print("""            </br>""")
        print("""            Week of %s:""" % week)
        print("""            <i>%s</i>""" % artist)
        print("""          </font>""")
        print("""        </td>""")
        print("""      </tr>""")

        if artist in ('VACATION','MARATHON'):
            continue

        td = time.strptime(week, '%Y-%m-%d')
        t0 = time.mktime(td)
        shows = []
        plays = []
        for x in range(5):

            t = t0 + 3600*24*x;
            d = time.strftime('%Y-%m-%d', time.localtime(t))
            res = cur.execute("""SELECT show_num FROM shows WHERE date='%s'"""
                          % d)
            r = res.fetchone()
            if not r:
                print()
                continue
            show_num = r[0]
            #print(" ", show_num)
            shows.append(show_num)
            r = find_tracks(artist, show_num)
            if r:
                print("""      <tr>""")
                print("""        <td>""")
                print("""          """ + ["Mon", "Tue", "Wed", "Thu", "Fri"][x])
                print("""        </td>""")
                print("""        <td>""")
                print("""          """+r[2])
                print("""        </td>""")
                l = make_play_link(show_num, r[-1])
                if l:
                    print("""        <td>""")
                    print("""          <a href="%s">""" % l)
                    print("""            play""")
                    print("""          </a>""")
                    print("""        </td>""")
                print("""      </tr>""")
    print("""    </table>""")
    print("""  </body>""")
    print("""</html>""")

if __name__ == '__main__':
    find_aotw_plays()
