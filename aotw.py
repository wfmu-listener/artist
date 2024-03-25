#!/usr/bin/env python
import requests
import time
from bs4 import BeautifulSoup as bs

base = 'https://www.wfmu.org'

output = open('/home/cgw/Hack/AOTW/aotw.txt','a')
for year in range(2018, 2024):
    rep = requests.get(base + '/playlists/WA%s' % year)
    s = bs(rep.content, 'html.parser')
    div = s.find('div', class_='showlist')
    for li in div.find_all('li'):
        date = li.text.strip().split(':')[0]
        td = time.strptime(date, '%B %d, %Y')
        date = time.strftime('%Y-%m-%d', td)
        print(date)
        url = li.find_all('a', href=True)[1]['href'] # skip ★
        show_num = url.split('/')[-1]
        rep = requests.get(base + url)
        s = bs(rep.content, 'html.parser')
        tab = s.find_all(id='drop_table')[0]
        rows = tab.find_all('tr')
        done = False
        for row in rows:
            if done:
                break
            text = row.text.strip()
            for line in text.splitlines():
                text = line.strip()
                lower = text.lower()
                if 'animal' in lower and 'of the' in lower:
                    line = date + ' | ' +  show_num + ' | ' + text
                    print(line)
                    output.write(line + '\n')
                    output.flush()
                    done = True
                    break
