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
import MySQLdb as mdb
from config import config as c

print c



global con
global cur
con = mdb.connect(c['db_host'], c['db_user'], c['db_pass'])
cur = con.cursor()


def handle_post(post):
    p = convert_post_to_dict(post)
    print p['ID']
    print p['post_title']
    if p['post_type'] == 'attachment':
        relative_file_path = p['guid'].split('wp-content/uploads/')[1]
        check_image_on_disk(relative_file_path)

    sys.exit()


def convert_post_to_dict(post):
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


def check_image_on_disk(image_path):
    print image_path

if __name__ == '__main__':
    qry = """SELECT * FROM `%s`.`%sposts` WHERE """ % (c['db_name'], c['wp_table_prefix'])
    qry += '(`guid` LIKE "%' + c['current_image_url_path'] + '%" AND `post_type`="attachment" ) OR '
    qry += '(`post_content` LIKE "%' + c['current_image_url_path'] + '%");'
    cur.execute(qry)
    data = cur.fetchall()
    for p in data:
        handle_post(p)
