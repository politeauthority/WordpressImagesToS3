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
import re
import boto
from config import config as c


SUPPORTED_MEDIA_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif']
global con
global cur
con = mdb.connect(c['db_host'], c['db_user'], c['db_pass'])
cur = con.cursor()


class WordpressToS3(object):

    def __init__(self):
        self.args = {
            'verbose': False
        }
        self.s3_connection = None
        self.s3_bucket = None
        self.images_found_on_disk = 0
        self.images_not_found_on_disk = 0
        self.images_found_on_s3 = 0
        self.images_not_found_on_s3 = 0
        self.images_found_similiar_to_db_update_to_s3 = set()
        self.images = {}

    def run(self):
        self.data = self.get_posts_sql()
        print 'Verifying %s potential media records' % len(self.data)
        for post in self.data:
            self.find_work(post)
            print ''
            # break

        print 'Images Found on Disk     : %s' % self.images_found_on_disk
        print 'Images Not Found on Disk : %s' % self.images_not_found_on_disk
        print 'Images Found on S3       : %s' % self.images_found_on_s3
        print 'Images Not Found on S3   : %s' % self.images_not_found_on_s3
        self.do_work()

    def find_work(self, post):
        p = self.convert_post_to_dict(post)
        image_on_disk = None
        image_on_s3 = None
        images = set()
        if p['post_type'] == 'attachment':
            print p['guid']
            images.update([p['guid'].split('wp-content/uploads/')[1]])
        elif p['post_type'] in ['post', 'revision']:
            print p['post_title']
            images.update(self.find_images_in_post_content(p['post_content']))
        else:
            print '[ERROR] UNKNOWN post_type %s' % p['post_type']
            sys.exit()
        # Go Through found images and look for similar ones
        post_images = {}
        for i in images:
            images_on_disk = self.check_image_on_disk(i, True)
            if images_on_disk:
                for fi in images_on_disk:
                    post_images[fi] = {'disk': True, 's3': None, 'update_link': None}
                self.images_found_on_disk += len(images_on_disk)
            else:
                post_images[i] = {'disk': False, 's3': None, 'update_link': None}
                self.images_not_found_on_disk += +1

        for base_url, info in post_images.iteritems():
            image_on_s3 = self.check_image_on_s3(base_url)
            if image_on_s3:
                self.images_found_on_s3 += 1
                post_images[i]['s3'] = True
            else:
                self.images_not_found_on_s3 += 1
            self.images[base_url] = info
        return None

    def get_posts_sql(self):
        """Find Work Method"""
        qry = """SELECT * FROM `%s`.`%sposts` WHERE """ % (c['db_name'], c['wp_table_prefix'])
        qry += '(`guid` LIKE "%' + c['current_image_url_path'] + '%" AND `post_type`="attachment" )'
        # qry += ' OR '
        # qry += '(`post_content` LIKE "%' + c['current_image_url_path'] + '%") '
        qry += 'AND `post_date` >= "2016-06-01" ;'
        print qry
        cur.execute(qry)
        data = cur.fetchall()
        return data

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

    def find_images_in_post_content(self, post_content):
        found_images = [m.start() for m in re.finditer(c['current_image_url_path'], post_content)]
        imgs_to_download = set()
        for img in found_images:
            segment = post_content[img:]
            segment2 = segment[: segment.find('>')]
            segment2 = segment2.replace('"', '')
            segment2 = segment2.replace("'", '')
            segment2 = segment2.split(' ')[0]
            segment2 = segment2.replace(c['current_image_url_path'], '')
            imgs_to_download.update([segment2])
        return imgs_to_download

    def check_image_on_disk(self, image_url, check_similar=False):
        """ Find Work Method """
        full_path = os.path.join(
            c['local_install_path'],
            'wp-content/uploads/',
            image_url
        )
        image_dir = full_path[:full_path.rfind('/')]
        image_name = full_path[full_path.rfind('/')+1:]
        found_images = []
        if check_similar:
            similiar_images = self.find_similar_images(image_dir, image_name)
            if similiar_images:
                found_images = similiar_images

        if not os.path.exists(full_path):
            if self.args['verbose']:
                print '[MISSING] on disk %s' % full_path
            return False
        if self.args['verbose']:
            print '[FOUND] on disk %s' % full_path
        found_images.append(image_url)
        return found_images

    def find_similar_images(self, image_dir, image_name):
        similiar_images = []
        print 'looking for similr'
        for m in SUPPORTED_MEDIA_EXTENSIONS:
            image_name = image_name.replace(m, '')
        if not os.path.exists(image_dir):
            return None
        for phile in os.listdir(image_dir):
            if image_name in phile:
                similiar_images.append(
                    os.path.join(
                        image_dir.replace(c['local_install_path'], ''),
                        phile)
                )
                # print phile
        return similiar_images

    def check_image_on_s3(self, image_url):
        s3_url = c['s3_image_url_path'] + image_url
        r = requests.get(s3_url)
        if r.status_code == 200:
            if self.args['verbose']:
                print '[FOUND] on s3 %s' % s3_url
            return True
        else:
            print 'ERROR: got status code %s from S3 for %s' % (r.status_code, s3_url)
            return False

    def do_work(self):
        self.s3_connection = boto.connect_s3(c['aws_access_key'], c['aws_secret_key'])
        self.s3_bucket = self.s3_connection.lookup(c['aws_bucket_name'])
        for image, info in self.images.iteritems():
            if info['disk'] and not info['s3']:
                print image
                print info
                self.upload_to_s3_from_disk(image)
                self.rewrite_url(images[image])

    def upload_to_s3_from_disk(self, image):
        print 'Up loadin!'
        local_path = os.path.join(
            c['local_install_path'],
            image
            )
        remote_path = "%s/%s" % (c['aws_blog_dir'], image.replace('wp-content/uploads', ''))
        print local_path
        print remote_path

        key = boto.s3.key.Key(self.s3_bucket)
        key.name = image
        key.key = remote_path
        key.make_public()
        url = key.generate_url(expires_in=0, query_auth=False)
        print "[UPLOADED] %s" % url
        self.images[image]['s3'] = True
        self.images[image]['update_link'] = True
        sys.exit()
        return url

    def rewrite_url(self, info):
        print info
        sys.exit()

if __name__ == '__main__':
    WordpressToS3().run()

# End File: wordpress_images_to_s3.py
