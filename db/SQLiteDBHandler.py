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

    def query(self, q: str):
        return self.__execute_read(q)

    def get_boards(self):
        return self.__execute_read('SELECT * FROM `boards`;')

    def get_users(self):
        return self.__execute_read('SELECT * FROM `users`;')

    def get_posts(self, after: int=0):
        if after == 0:
            return self.__execute_read('SELECT * FROM `posts`;')
        return self.__execute_read(
            'SELECT * FROM `posts` WHERE `date_time` >= :after ;',
            { 'after': after })

    def get_pushes(self, after: int=0):
        if after == 0:
            return self.__execute_read('SELECT * FROM `pushes`;')
        return self.__execute_read(
            'SELECT * FROM `pushes` WHERE `date_time` >= :after ;',
            { 'after': after })

    def get_board_id(self, board: str) -> int:
        return self.__execute_read(
            'SELECT `id` FROM `boards` WHERE `name` = :board ;',
            { 'name': board }
        )

    def get_user_id(self, username: str) -> int:
        return self.__execute_read(
            'SELECT `id` FROM `users` WHERE `username` = :username ;',
            { 'username': username }
        )

    def get_post(self, board, index: int):
        if isinstance(board, int):
            return self.__execute_read(
                'SELECT * FROM `posts` WHERE `board` = :board AND `index` = :index ;',
                { 'board': board, 'index': index }
            )
        return self.__execute_read('''
SELECT * FROM `posts`
WHERE `board` = (
    SELECT `id` FROM `boards`
    WHERE `name` = :board
) AND `index` = :index ;''',
            { 'board': board, 'index': index}
        )

    def get_post_pushes(self, board, index: int):
        if isinstance(board, int):
            return self.__execute_read('''
SELECT * FROM `pushes`
WHERE `post` = (
    SELECT `id` FROM `posts`
    WHERE `board` = :board
        AND `index` = :index
);
            ''', { 'board': board, 'index': index })
        return self.__execute_read('''
SELECT * FROM `pushes`
WHERE `post` = (
    SELECT `id` FROM `posts`
    WHERE `board` = (
        SELECT `id` FROM `boards`
        WHERE `name` = :board
    ) AND `index` = :index
);
        ''', { 'board': board, 'index': index })

    def get_posts_by_user_id(self, user_id: int, after: int=0):
        if after == 0:
            return self.__execute_read(
                'SELECT * FROM `posts` WHERE `author` = :user_id ;',
                { 'user_id': user_id }
            )
        return self.__execute_read(
            'SELECT * FROM `posts` WHERE `author` = :user_id AND `date_time` >= :after ;',
            { 'user_id': user_id, 'after': after }
        )

    def get_posts_by_username(self, username: str, after: int=0):
        if after == 0:
            return self.__execute_read('''
SELECT * FROM `posts`
WHERE `author` = (
    SELECT `id` FROM `users`
    WHERE `username` = :username
);''', { 'username': username })
        return self.__execute_read('''
SELECT * FROM `posts`
WHERE `author` = (
    SELECT `id` FROM `users`
    WHERE `username` = :username
) AND `date_time` >= :after ;''', { 'username': username, 'after': after })

    def get_posts_by_ip(self, ip: str):
        return self.__execute_read('SELECT * FROM `posts` WHERE `ip` = :ip ;', { 'ip': ip })

    def get_pushes_by_user_id(self, user_id: int, after: int=0):
        if after == 0:
            return self.__execute_read(
                'SELECT * FROM `pushes` WHERE `author` = :user_id ;',
                { 'user_id': user_id }
            )
        return self.__execute_read(
            'SELECT * FROM `pushes` WHERE `author` = :user_id AND `date_time` > :after ;',
            { 'user_id': user_id, 'after': after }
        )

    def get_pushes_by_username(self, username: str, after: int=0):
        if after == 0:
            return self.__execute_read('''
SELECT * FROM `pushes`
WHERE `author` = (
    SELECT `id` FROM `users`
    WHERE `username` = :username
);''', { 'username': username })
        return self.__execute_read('''
SELECT * FROM `pushes`
WHERE `author` = (
    SELECT `id` FROM `users`
    WHERE `username` = :username
) AND `date_time` >= :after ;''', { 'username': username, 'after': after })

    def get_pushes_by_ip(self, ip: str):
        return self.__execute_read('SELECT * FROM `pushes` WHERE `ip` = :ip ;', { 'ip': ip })

    def add_user(self, user: str):
        try:
            self.__execute_write('''
INSERT INTO `users` (`username`)
VALUES ( :user );''', {'user': user})
        except:
            pass

    def add_board(self, board: str):
        try:
            self.__execute_write('''
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

        self.__execute_write('''
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
            self.__execute_write('''
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
            self.__execute_write('''
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
                self.__execute_write('''
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

        self.__execute_write('''
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
);
            ''',
            {
                'board': board,
                'index': index,
                'date_time': get_current_time()
            })

    def __execute_read(self, *args, **kwargs):
        with self.__execution_lock:
            return self.__conn.execute(*args, **kwargs).fetchall()

    def __execute_write(self, *args, **kwargs):
        with self.__execution_lock:
            self.__conn.execute(*args, **kwargs)
            self.__op_count_increment()

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
`index_boards_id` ON `boards`(`id`);''')
        self.__conn.execute('''
CREATE UNIQUE INDEX IF NOT EXISTS
`index_boards_name` ON `boards`(`name`);''')

        # table `users`
        self.__conn.execute('''
CREATE TABLE IF NOT EXISTS `users`
(
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `username` TEXT UNIQUE NOT NULL
);''')
        self.__conn.execute('''
CREATE UNIQUE INDEX IF NOT EXISTS
`index_users_id` ON `users`(`id`);''')
        self.__conn.execute('''
CREATE UNIQUE INDEX IF NOT EXISTS
`index_users_username` ON `users`(`username`);''')

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
`index_posts_id` ON `posts`(`id`);''')
        self.__conn.execute('''
CREATE UNIQUE INDEX IF NOT EXISTS
`index_posts_post_id` ON `posts`(`post_id`);''')
        self.__conn.execute('''
CREATE INDEX IF NOT EXISTS
`index_posts_author` ON `posts`(`author`);''')
        self.__conn.execute('''
CREATE INDEX IF NOT EXISTS
`index_posts_date_time` ON `posts`(`date_time`);''')
        self.__conn.execute('''
CREATE INDEX IF NOT EXISTS
`index_posts_ip` ON `posts`(`ip`);''')

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
`index_posts_content_id` ON `posts_content`(`id`);''')
        self.__conn.execute('''
CREATE UNIQUE INDEX IF NOT EXISTS
`index_posts_content_post` ON `posts_content`(`post`);''')

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
`index_pushes_id` ON `pushes`(`id`);''')
        self.__conn.execute('''
CREATE INDEX IF NOT EXISTS
`index_pushes_post` ON `pushes`(`post`);''')
        self.__conn.execute('''
CREATE INDEX IF NOT EXISTS
`index_pushes_type` ON `pushes`(`type`);''')
        self.__conn.execute('''
CREATE INDEX IF NOT EXISTS
`index_pushes_author` ON `pushes`(`author`);''')
        self.__conn.execute('''
CREATE INDEX IF NOT EXISTS
`index_pushes_ip` ON `pushes`(`ip`);''')
        self.__conn.execute('''
CREATE INDEX IF NOT EXISTS
`index_pushes_date_time` ON `pushes`(`date_time`);''')

        # table `crawled_posts`
        self.__conn.execute('''
CREATE TABLE IF NOT EXISTS `crawled_posts`
(
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `post` INTEGER UNIQUE NOT NULL,
    `date_time` NOT NULL,
    FOREIGN KEY (`post`) REFERENCES `posts`(`id`)
);''')
        self.__conn.execute('''
CREATE UNIQUE INDEX IF NOT EXISTS
`index_crawled_posts_id` ON `crawled_posts`(`id`);''')
        self.__conn.execute('''
CREATE UNIQUE INDEX IF NOT EXISTS
`index_crawled_posts_post` ON `crawled_posts`(`post`);''')
        self.__conn.execute('''
CREATE INDEX IF NOT EXISTS
`index_crawled_posts_date_time` ON `crawled_posts`(`date_time`);''')

    def __enter__(self):
        self.__conn = sqlite3.connect(self.__path)
        # enables foreign key constraint support
        self.__conn.execute('PRAGMA foreign_key = ON;')
        self.__create_tables()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.__conn.commit()
        self.__conn.close()
