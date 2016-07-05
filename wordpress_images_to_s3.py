"""
    Configuration Options
    db_host
    db_user
    db_pass
    db_name
    wp_table_prefix = 'wp_'
    local_install_path
    current_image_url_path
    s3_image_url_path = ''
"""

import sys
import os
import MySQLdb as mdb
import requests
from config import config as c


SUPPORTED_MEDIA_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif']
global con
global cur
con = mdb.connect(c['db_host'], c['db_user'], c['db_pass'])
cur = con.cursor()


class WordpressToS3(object):

    def __init__(self):
        self.args = {
            'verbose': True
        }
        self.images_found_on_disk = 0
        self.images_found_on_s3 = 0
        self.images_found_similiar_to_db_update_to_s3 = set()

    def run(self):
        self.data = self.get_posts()
        print 'Checking %s posts containing images' % len(self.data)
        for post in self.data:
            self.handle_post(post)
            break
        print 'Images Found on Disk: %s' % self.images_found_on_disk
        print 'Images Found on S3: %s' % self.images_found_on_s3

    def get_posts(self):
        qry = """SELECT * FROM `%s`.`%sposts` WHERE """ % (c['db_name'], c['wp_table_prefix'])
        qry += '(`guid` LIKE "%' + c['current_image_url_path'] + '%" AND `post_type`="attachment" )'
        qry += ' OR '
        qry += '(`post_content` LIKE "%' + c['current_image_url_path'] + '%");'
        cur.execute(qry)
        data = cur.fetchall()
        return data

    def handle_post(self, post):
        p = self.convert_post_to_dict(post)
        image_on_disk = None
        image_on_s3 = None
        images = set()
        if p['post_type'] == 'attachment':
            print p['guid']
            images.update([p['guid'].split('wp-content/uploads/')[1]])
        elif p['post_type'] == 'post':
            print p['post_title']
            print self.find_images_in_post_content()
        else:
            print '[ERROR] UNKNOWN post_type %s' % p['post_type']
            sys.exit()
        print images
        # Go Through found images and look for similar ones
        for i in images:
            images_on_disk = self.check_image_on_disk(i)
            if image_on_disk:
                images.update(images_on_disk)
        print images
        for i in images:
            self.images_found_on_disk += 1
            image_on_s3 = self.check_image_on_s3(i)
            if image_on_s3:
                self.images_found_on_s3 += 1
        return None

    def convert_post_to_dict(self, post):
        p = {
            'ID': post[0],
            'post_author': post[1],
            'post_date': post[2],
            'post_date_gmt': post[3],
            'post_content': post[4],
            'post_title': post[5],
            'post_excerpt': post[6],
            'post_status': post[7],
            'comment_status': post[8],
            'ping_status': post[9],
            'post_password': post[10],
            'post_name': post[11],
            'to_ping': post[12],
            'pinged': post[13],
            'post_modified': post[14],
            'post_modified_gmt': post[15],
            'post_content_filtered': post[16],
            'post_parent': post[17],
            'guid': post[18],
            'menu_order': post[19],
            'post_type': post[20],
            'post_mime_type': post[21],
            'comment_count': post[22]
        }
        return p

    def find_images_in_post_content(self):
        return None

    def check_image_on_disk(self, image_url, check_similar=False):
        print image_url
        full_path = os.path.join(
            c['local_install_path'],
            'wp-content/uploads/',
            image_url
        )
        image_dir = full_path[:full_path.rfind('/')]
        image_name = full_path[full_path.rfind('/')+1:]
        if check_similar:
            similiar_images = self.find_similar_images(image_dir, image_name)
            if similiar_images:
                found_images = similiar_images
            else:
                found_images = []
        if not os.path.exists(full_path):
            if self.args['verbose']:
                print '[MISSING] on disk %s' % full_path
            return False
        if self.args['verbose']:
            print '[Found] on disk %s' % full_path
        found_images.append(full_path)
        return found_images

    def find_similar_images(self, image_dir, image_name):
        similiar_images = []
        for m in SUPPORTED_MEDIA_EXTENSIONS:
            image_name = image_name.replace(m, '')
        if not os.path.exists(image_dir):
            return None
        for phile in os.listdir(image_dir):
            if image_name in phile:
                similiar_images.append(image_dir+phile)
        return similiar_images

    def check_image_on_s3(self, image_url):
        s3_url = c['s3_image_url_path'] + image_url
        r = requests.get(s3_url)
        if r.status_code == 200:
            return True
        else:
            print 'ERROR: got status code %s from S3' % r.status_code
            return False

if __name__ == '__main__':
    WordpressToS3().run()
