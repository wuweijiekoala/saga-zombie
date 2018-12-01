from PTTLibrary.Information import PostInformation
from PTTLibrary.Information import PushInformation
from PTTLibrary.PTT import ErrorCode
from threading import Lock
import sqlite3
import time
import re


base_time = -int(time.mktime(time.strptime('', '')))
ptt_time_zone_offset = 28800
current_time_zone_offset = \
    int(time.mktime(time.localtime())) - \
    int(time.mktime(time.gmtime()))


def get_current_time() -> int:
    return int(time.mktime(time.gmtime()))


def get_post_time(post: PostInformation) -> int:
    try:
        return int(
            time.mktime(
                time.strptime(
                    post.getDate().strip(),
                    '%a %b %d %H:%M:%S %Y'
                )
            )
        ) - current_time_zone_offset + ptt_time_zone_offset
    except:
        return 0


def get_post_year(post: PostInformation) -> int:
    try:
        return int(
            time.mktime(
                time.strptime(
                    post.getDate().strip()[20:],
                    '%Y'
                )
            )
        ) - current_time_zone_offset + ptt_time_zone_offset
    except:
        return 0


def get_push_time(year: int, push: PushInformation):
    try:
        return int(
            time.mktime(
                time.strptime(
                    push.getTime(),
                    '%m/%d %H:%M'
                )
            )
        ) + base_time + year - current_time_zone_offset + ptt_time_zone_offset
    except:
        return year


def get_post_author_id(post: PostInformation) -> str:
    try:
        return get_post_author_id.pattern.match(post.getAuthor().strip()).group(1)
    except:
        return ''
get_post_author_id.pattern = re.compile('^([a-zA-Z0-9]*)')


class SQLiteDBHandler:
    def __init__(self, path):
        self.__path = path
        self.__max_op_count = 10000
        self.__op_count = 0
        self.__execution_lock = Lock()
        self.__counter_lock = Lock()
        self.__commit_lock = Lock()

    def add_user(self, user: str):
        try:
            self.__execute('''
INSERT INTO `users` (`username`)
VALUES ( :user );''', {'user': user})
        except:
            pass

    def add_board(self, board: str):
        try:
            self.__execute('''
INSERT INTO `boards` (`name`)
VALUES ( :board );''', {'board': board})
        except:
            pass

    def insert_or_update_post(self, post: PostInformation, index: int):
        if post is None or index is None:
            return
        if post.getDeleteStatus == ErrorCode.PostDeleted:
            return

        author = get_post_author_id(post)
        board = post.getBoard()
        delete_status = post.getDeleteStatus()
        self.add_user(author)
        self.add_board(board)

        self.__execute('''
INSERT OR REPLACE INTO `posts`
(
    `id`,
    `board`,
    `index`,
    `post_id`,
    `author`,
    `date_time`,
    `title`,
    `web_url`,
    `money`,
    `ip`,
    `delete_state`
)
VALUES
(
    (
        SELECT `id` FROM `posts`
        WHERE `board` = (
                SELECT `id` FROM `boards`
                WHERE `name` = :board
            )
            AND `index` = :index
    ),
    (
        SELECT `id` FROM `boards`
        WHERE `name` = :board
    ),
    :index,
    :post_id,
    (
        SELECT `id` FROM `users`
        WHERE `username` = :author
    ),
    :date_time,
    :title,
    :web_url,
    :money,
    :ip,
    :delete_state
);
            ''',
            {
                'board': board,
                'index': index,
                'post_id': post.getID(),
                'author': author,
                'date_time': get_post_time(post),
                'title': post.getTitle(),
                'web_url': post.getWebUrl(),
                'money': post.getMoney(),
                'ip': post.getIP(),
                'delete_state': delete_status
            }
        )

        if delete_status == 0:
            self.__execute('''
INSERT OR REPLACE INTO `posts_content`
(`id`, `post`, `content`)
VALUES
(
    (
        SELECT `id` FROM `posts_content`
        WHERE `post` = (
            SELECT `id` FROM `posts`
            WHERE `board` = (
                SELECT `id` FROM `boards`
                WHERE `name` = :board
            ) AND `index` = :index
        )
    ),
    (
        SELECT `id` FROM `posts`
        WHERE `board` = (
            SELECT `id` FROM `boards`
            WHERE `name` = :board
        ) AND `index` = :index
    ),
    :content
);
                ''',
                {
                    'board': board,
                    'index': index,
                    'content': post.getContent()
                }
            )

            # delete existing pushes
            self.__execute('''
DELETE FROM `pushes`
WHERE `post` = (
    SELECT `id` FROM `posts`
    WHERE `board` = (
        SELECT `id` FROM `boards`
        WHERE `name` = :board
    ) AND `index` = :index
);
            ''',
                {
                    'board': board,
                    'index': index
                })

            year = get_post_year(post)
            for push in post.getPushList():
                author = push.getAuthor()
                self.add_user(author)
                self.__execute('''
INSERT INTO `pushes`
(
    `post`,
    `type`,
    `author`,
    `content`,
    `ip`,
    `date_time`
)
VALUES
(
    (
        SELECT `id` FROM `posts`
        WHERE `board` = (
            SELECT `id` FROM `boards`
            WHERE `name` = :board
        ) AND `index` = :index
    ),
    :type ,
    (
        SELECT `id` FROM `users`
        WHERE `username` = :author
    ),
    :content ,
    :ip ,
    :date_time
)
                    ''',
                    {
                        'board': board,
                        'index': index,
                        'type': push.getType(),
                        'author': push.getAuthor(),
                        'content': push.getContent(),
                        'ip': push.getIP(),
                        'date_time': get_push_time(year, push)
                    })

        self.__execute('''
INSERT OR REPLACE INTO `crawled_posts`
(`id`, `post`, `date_time`)
VALUES
(
    (
        SELECT `id` FROM `crawled_posts`
        WHERE `post` = (
            SELECT `id` FROM `posts`
            WHERE `board` = (
                SELECT `id` FROM `boards`
                WHERE `name` = :board
            ) AND `index` = :index
        )
    ),
    (
        SELECT `id` FROM `posts`
        WHERE `board` = (
            SELECT `id` FROM `boards`
            WHERE `name` = :board
        ) AND `index` = :index
    ),
    :date_time
)
            ''',
            {
                'board': board,
                'index': index,
                'date_time': get_current_time()
            })

    def __execute(self, *args, **kwargs):
        with self.__execution_lock:
            result = self.__conn.execute(*args, **kwargs)
            self.__op_count_increment()
            return result

    def __op_count_increment(self):
        with self.__counter_lock:
            self.__op_count += 1
            if self.__op_count >= self.__max_op_count:
                self.__commit_now()
                self.__op_count = 0

    def __commit_now(self):
        with self.__commit_lock:
            self.__conn.commit()

    def __create_tables(self):
        # table `boards`
        self.__conn.execute('''
CREATE TABLE IF NOT EXISTS `boards`
(
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `name` TEXT UNIQUE NOT NULL
);''')
        self.__conn.execute('''
CREATE UNIQUE INDEX IF NOT EXISTS
`index_boards_id` on `boards`(`id`);''')
        self.__conn.execute('''
CREATE UNIQUE INDEX IF NOT EXISTS
`index_boards_name` on `boards`(`name`);''')

        # table `users`
        self.__conn.execute('''
CREATE TABLE IF NOT EXISTS `users`
(
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `username` TEXT UNIQUE NOT NULL
);''')
        self.__conn.execute('''
CREATE UNIQUE INDEX IF NOT EXISTS
`index_users_id` on `users`(`id`);''')
        self.__conn.execute('''
CREATE UNIQUE INDEX IF NOT EXISTS
`index_users_username` on `users`(`username`);''')

        # table `posts`
        self.__conn.execute('''
CREATE TABLE IF NOT EXISTS `posts`
(
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `board` INTEGER NOT NULL,
    `index` INTEGER NOT NULL,
    `post_id` TEXT UNIQUE,
    `author` INTEGER NOT NULL,
    `date_time` INTEGER,
    `title` TEXT,
    `web_url` TEXT,
    `money` INTEGER,
    `ip` TEXT,
    `delete_state` INTEGER NOT NULL,
    UNIQUE (`board`, `index`),
    FOREIGN KEY (board) REFERENCES board(id),
    FOREIGN KEY (author) REFERENCES users(id)
);''')
        self.__conn.execute('''
CREATE UNIQUE INDEX IF NOT EXISTS
`index_posts_id` on `posts`(`id`);''')
        self.__conn.execute('''
CREATE UNIQUE INDEX IF NOT EXISTS
`index_posts_post_id` on `posts`(`post_id`);''')
        self.__conn.execute('''
CREATE INDEX IF NOT EXISTS
`index_posts_author` on `posts`(`author`);''')
        self.__conn.execute('''
CREATE INDEX IF NOT EXISTS
`index_posts_date_time` on `posts`(`date_time`);''')
        self.__conn.execute('''
CREATE INDEX IF NOT EXISTS
`index_posts_ip` on `posts`(`ip`);''')

        # table `post_content`
        self.__conn.execute('''
CREATE TABLE IF NOT EXISTS `posts_content`
(
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `post` INTEGER UNIQUE NOT NULL,
    `content` TEXT NOT NULL,
    FOREIGN KEY (post) REFERENCES posts(id)
);''')
        self.__conn.execute('''
CREATE UNIQUE INDEX IF NOT EXISTS
`index_posts_content_id` on `posts_content`(`id`);''')
        self.__conn.execute('''
CREATE UNIQUE INDEX IF NOT EXISTS
`index_posts_content_post` on `posts_content`(`post`);''')

        # table `pushes`
        self.__conn.execute('''
CREATE TABLE IF NOT EXISTS `pushes`
(
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `post` INTEGER NOT NULL,
    `type` INTEGER NOT NULL,
    `author` INTEGER NOT NULL,
    `content` TEXT NOT NULL,
    `ip` TEXT,
    `date_time` INTEGER NOT NULL
);''')
        self.__conn.execute('''
CREATE INDEX IF NOT EXISTS
`index_pushes_id` on `pushes`(`id`);''')
        self.__conn.execute('''
CREATE INDEX IF NOT EXISTS
`index_pushes_post` on `pushes`(`post`);''')
        self.__conn.execute('''
CREATE INDEX IF NOT EXISTS
`index_pushes_type` on `pushes`(`type`);''')
        self.__conn.execute('''
CREATE INDEX IF NOT EXISTS
`index_pushes_author` on `pushes`(`author`);''')
        self.__conn.execute('''
CREATE INDEX IF NOT EXISTS
`index_pushes_ip` on `pushes`(`ip`);''')
        self.__conn.execute('''
CREATE INDEX IF NOT EXISTS
`index_pushes_date_time` on `pushes`(`date_time`);''')

        # table `crawled_posts`
        self.__conn.execute('''
CREATE TABLE IF NOT EXISTS `crawled_posts`
(
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `post` INTEGER UNIQUE NOT NULL,
    `date_time` NOT NULL,
    FOREIGN KEY (post) REFERENCES posts(id)
);''')
        self.__conn.execute('''
CREATE UNIQUE INDEX IF NOT EXISTS
`index_crawled_posts_post` on `crawled_posts`(`post`);''')
        self.__conn.execute('''
CREATE UNIQUE INDEX IF NOT EXISTS
`index_crawled_posts_date_time` on `crawled_posts`(`date_time`);''')

    def __enter__(self):
        self.__conn = sqlite3.connect(self.__path)
        # enables foreign key constraint support
        self.__conn.execute('PRAGMA foreign_key = ON;')
        self.__create_tables()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.__conn.commit()
        self.__conn.close()