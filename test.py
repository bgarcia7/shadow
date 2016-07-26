import urllib
from urllib2 import urlopen
import matplotlib.pyplot as plt
from pymongo import MongoClient
from bs4 import BeautifulSoup
from collections import defaultdict

base_url = 'https://ecommerce.shopify.com/'
forums_url = 'forums'

db_client = MongoClient()
data = db_client['shopify']['forum']
data2 = db_client['shopify_backup']
users = db_client['shopify']['users']

import re
import datetime as dt
months = ['january','february','march','april','may','june','july','august','september','october','november','december']

def get_date(post):
    
    regexes = ['(\d+) day','(\d+) month', '(\w+) (\d+), (20\d+)']
    raw_date = post.find('div',{'class':'date'}).text.strip()
    date = None
    
    for idx, reg in enumerate(regexes):
        matches = re.search(reg, raw_date)
        if matches:
            if idx == 0:
                date = dt.datetime.now() - dt.timedelta(days=int(matches.group(1)))
            elif idx == 1:
                date = dt.datetime.now() - dt.timedelta(days=int(matches.group(1))*30)
            else:
                date = dt.datetime(int(matches.group(3)), int(months.index(matches.group(1).lower())) + 1, int(matches.group(2)))

    return date.strftime('%Y-%m-%d') if date else None


def process_post(post):
    
    user = post.find('div',{'class':'author'})
    user_id = int(user.find('a',{'class':'username'}).get('href').split('/')[-1])
    
    # Add user to db if does not exist 
    if users.find({'id': user_id}).count() < 1:
        name = user.find('a',{'class':'username'}).text.strip()
        title = user.find_all('em')[0].text.strip().lower()
        site = user.find_all('em')[-1].text.strip().lower()
        posts = int(user.find('div',{'class':'stats'}).find('a').text.strip().lower())
        users.insert_one({'id':user_id,'name':name,'title':title,'site':site, 'posts':posts })
        
    # Extract date
    date = get_date(post)
    
    # Extract text
    text = ' '.join([txt.text.lower() for txt in post.find('div',{'itemprop':'description'}).find_all('p')])
    
    return user_id, text, date
    
count = 0
for category in data.find():
    
    print ''
    for sub_cat_key in category["sub_cats"]:
        
        print 'SUBCATEGORY: {sub_cat}'.format(sub_cat=sub_cat_key)

        
        sub_cat = category['sub_cats'][sub_cat_key]
        posts = []
        
        
        # Run through each thread
        for idx, url in enumerate(sub_cat['topic_urls']):

            try:
                topic_page = BeautifulSoup(urlopen(url))
                thread = []

                # Process original post
                user_id, text, date = process_post(topic_page.find('div',{'class':'original-post'}))
                thread.append({'user_id':user_id, 'date':date, 'text':text})

                # Process each reply
                for reply in topic_page.find_all('div',{'itemtype':'http://schema.org/UserComments'}):
                    user_id, text, date = process_post(reply)
                    thread.append({'user_id':user_id, 'date':date, 'text':text})

                posts.append(thread)

                # Status Update
                if (idx+1) % 5 == 0:
                    print 'PROCESSED {idx}/{total} posts'.format(idx=(idx+1),total=len(sub_cat['topic_urls']))

            except Exception as e:
                print 'ERROR IN SUBCATEGORY: ', str(e)

        category["sub_cats"][sub_cat_key]['posts'] = posts
  
        data.update_one({"_id":category["_id"]},{'$set':category})  

        count +=1

        print 'JUST UPDATED CATEGORY:', str(count)   
    