import re
import itertools
import datetime as dt
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
import requests


def read_all_links(url):
    """Scrape a page from NRCan for links to daily price tables"""
    mp = requests.get(url).content
    soup = BeautifulSoup(mp, 'html.parser')
    raw_links = soup.find_all('a', href=True)
    all_links = [{'title': lnk.string, 'url': lnk.get('href')} for lnk in raw_links]
    # everything I want is "<Month> <Year>" so split title should be length 2
    all_links = [lnk for lnk in all_links if len(str.split(str(lnk['title']))) == 2]
    # Now I can just make sure the second element is a digit and that should get just
    # The year month ones instead of "Earth Sciences" for example
    all_links = [lnk for lnk in all_links if str.split(lnk['title'])[1].isdigit()]
    # 2014 has 4 Months of a discontinued series, easiest to remove them manually I think
    bad_urls = [
        'https://www.nrcan.gc.ca/energy/fuel-prices/crude/15894',
        'https://www.nrcan.gc.ca/energy/fuel-prices/crude/15707',
        'https://www.nrcan.gc.ca/energy/fuel-prices/crude/18535',
        'https://www.nrcan.gc.ca/energy/fuel-prices/crude/14456'
    ]
    all_links = [lnk for lnk in all_links if lnk['url'] not in bad_urls]
    return all_links


def read_all_pages():
    """Scrape 3 pages of links from NRCan for monthly series links"""
    urls = [
        'https://www.nrcan.gc.ca/energy/oil-sands/18087', # main page
        'https://www.nrcan.gc.ca/energy/fuel-prices/crude/18122', # 2015
        'https://www.nrcan.gc.ca/energy/fuel-prices/crude/16993' # 2014
        # Can add more here if NRCAN fixes their archive links or I find where they're archived
    ]
    page_lists = [read_all_links(url) for url in urls]
    combined = list(itertools.chain.from_iterable(page_lists))
    combined_dict = {it['title']: it['url'] for it in combined}
    # This link breaks for some reason, another fun hacky patch
    combined_dict['December 2015'] = 'https://www.nrcan.gc.ca/energy/fuel-prices/crude/17963'
    return combined_dict


def normalize_cols(df):
    """clean up column names"""
    df = df.copy()
    df.columns = ['_'.join(re.sub(r"[,\*]", '', col).split()).lower() for col in df.columns]
    df = df.reindex(sorted(df.columns), axis=1)
    return df


def reindex_dates(df):
    """Take the date column and turn it to a datetime index"""
    df = (
        df
        .copy()
        .assign(Date=lambda df: pd.to_datetime(df['Date'], errors='coerce'))    
    )
    # First date of the June 2017 page is wrong
    # Also all the weekends are blank on it, unlike every other page
    # so we have another hacky fix to deal with that
    if df.iloc[1]['Date'] == dt.datetime(2017, 6, 2):
        df.loc[0, 'Date'] = dt.datetime(2017, 6, 1)
        df = (
            df
            .dropna(subset=['Date'])
            .set_index('Date')
            .reindex(pd.date_range(
                start=df['Date'].min(),
                end=df['Date'].max(),
                freq='1D')
            )
        )
    else:
        df = df.set_index('Date').sort_index()
    return df


def read_df(link):
    """Read a month of data into a dataframe"""
    # Drop the average row, and the filler row at the top if it's there
    badrows = ['Average', '$ Cdn/m3']
    df = (
        pd.read_html(link, header=0)[0]
        .query('Date not in @badrows')
        .pipe(reindex_dates)
        .pipe(normalize_cols)
        .apply(pd.to_numeric, errors='coerce')
    )
    return df


def read_all_dfs():
    """Now do it for all the months and put them in one big dataframe"""
    links = read_all_pages()
    df_list = [read_df(links[key]) for key in links.keys()]
    df_fin = pd.concat(df_list, sort=True).sort_index()
    return df_fin


if __name__ == '__main__':
    df = read_all_dfs()
    df.to_csv('nrcan.csv')
