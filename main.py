import re
import urllib3
from lxml.html import fromstring
import requests
from urllib.robotparser import RobotFileParser
import time
from urllib.parse import urlparse

urllib3.disable_warnings()


def doi_crawler(doi_file_path):
    with open(doi_file_path, 'r', encoding='utf-8') as fp:
        html = fp.read()
        html_tree = fromstring(html)
        dois_html = html_tree.xpath('//b[text()="DOI:"]/following::*[1]')
        dois = []
        for doi_html in dois_html:
            dois.append(doi_html.text)
        return dois


def paper_clawer(dois):
    send_headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, "
                                  "like Gecko) Chrome/107.0.0.0 Safari/537.36"}
    robot_url = 'https://sci-hub.wf/robots.txt'
    try:
        rp = RobotFileParser()
        rp.set_url(robot_url)
        rp.read()
    except Exception as e:
        print('get_robot_parser() error: ', e)
    domains = {}
    download_cnt = 0
    for doi in dois:
        url = 'https://sci-hub.wf/{}'.format(doi)
        wait_time(url, domains)
        html = download_web_page(url, send_headers, num_retries=2)
        paper_title_href = get_title_href(html)
        if paper_title_href and download_pdf(paper_title_href, send_headers, doi, num_retries=2):
            download_cnt += 1

    print('%d of total %d pdf success' % (download_cnt, len(dois)))


def download_pdf(paper_title_href, headers, doi, num_retries):
    url = paper_title_href['href']
    components = urlparse(url)
    if len(components.scheme) == 0:
        url = 'https:{}'.format(url)
    try:
        rsp = requests.get(url, headers=headers, verify=False)
        if rsp.status_code >= 400:
            print("Download error: ", rsp.status_code)
            if num_retries and 500 <= rsp.status_code < 600:
                return download_pdf(paper_title_href, headers, num_retries - 1)
        title = paper_title_href['title']
        if len(title) < 5:
            title = re.sub(r'[^0-9A-Za-z\-,._;]', '_', doi)[:128] + ".pdf"
        else:
            title = re.sub(r'[^0-9A-Za-z\-,._;]', '_', title)[:128] + ".pdf"
        with open("./download-paper/" + title, 'wb') as fp:
            fp.write(rsp.content)
        print("Download success: ", title, "\n")
    except requests.exceptions.RequestException as e:
        print("Download error: ", e)
        return False
    return True


def get_title_href(html):
    try:
        tree = fromstring(html)
        onclick = tree.xpath('//div[@id="buttons"]/ul/li/a')[1].get('onclick')
        href = re.findall(r"location.href\s*=\s*'(.*?)'", onclick)[0].replace('\\', '')
        paper_title = tree.xpath('//div[@id="citation"]/i/text()')
        if len(paper_title) == 0:
            paper_title = tree.xpath('//div[@id="citation"]/text()')
        return {'title': paper_title[0], 'href': href}
    except Exception as e:
        print("Download failed: this paper may not be included in sci-hub.\n")
        return None


def wait_time(url, domains=None, delay=3):
    if domains is None:
        domains = {}
    domain = urlparse(url).netloc  # get the domain
    last_accessed = domains.get(domain)  # the time last accessed
    if delay > 0 and last_accessed is not None:
        sleep_secs = delay - (time.time() - last_accessed)
        if sleep_secs > 0:
            time.sleep(sleep_secs)
    domains[domain] = time.time()


def download_web_page(url, headers, num_retries):
    print("Downloading: ", url)
    try:
        rsp = requests.get(url, headers=headers, verify=False)
        html = rsp.text
        if rsp.status_code >= 400:
            print("Download fail: ", rsp.text)
            html = None
            if num_retries and 500 <= rsp.status_code < 600:
                return download_web_page(url, headers, num_retries - 1)
    except requests.exceptions.RequestException as e:
        print("Download error: ", e)
        return None
    return html


if __name__ == '__main__':
    # 获取文章doi编号列表
    doi_list = doi_crawler("./example-list.html")

    # 根据doi编号爬取文章
    paper_clawer(doi_list)
