import MySQLdb as mdb

db_host = ''
db_user = ''
db_pass = ''
db_name = 'blog_baird'
wp_table_prefix = 'wp_'
local_install_path = '/srv/wordpress/bairdwarner'
current_image_url_path = 'http://www.bairdwarner.com/blog/wp-content/uploads/'
s3_image_url_path = ''

global con
global cur
con = mdb.connect( dbhost, dbuser, dbpass )
cur = con.cursor()

if __name__ == '__main__':
	qry ="""SELECT * FROM `%s`.`%sposts` 
		WHERE 1=1"""
	posts = cur.execute(qry).fetchall()
	for p in posts:
		print p