import sqlite3
import time
import logging

# get Logger for this modul
logger = logging.getLogger(__name__)

class DiscordBase:
    def __init__(self):
        self.msg_id = None

        # Establish connection to SQLite database and create table
        self.conn = sqlite3.connect('hll_discord_helper.db', check_same_thread=False)  # Connection to the database
        self.cursor = self.conn.cursor()  # Cursor for SQL queries     

        self.create_Message_Table()
        self.create_Map_Vote_Table()
        self.migrate_Map_Vote_Table()
        self.create_Balance_Table()
        self.create_Voter_Table()
        self.create_Voter_Register_Table()
        self.create_Inappropriate_Name_Table()
        self.create_Key_Value()

    def create_Message_Table(self):
        # Creates the table if it does not yet exist
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            msg_seqno INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_sender TEXT,
            msg_id TEXT,
            msg_datetime INTEGER
        )
        ''')

        self.conn.commit()  

    def create_Map_Vote_Table(self):
        # Creates the table if it does not yet exist
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS map_vote (
            mapvot_seqno INTEGER PRIMARY KEY AUTOINCREMENT,
            mapvot_id INTEGER,
            mapvot_game_id INTEGER,
            mapvot_map_name TEXT,
            mapvot_start INTEGER,
            mapvot_end INTEGER
        )
        ''')
        self.conn.commit()  

    def migrate_Map_Vote_Table(self):

        if self.column_exists ("map_vote", "mapvot_game_id"):

            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS temp_map_vote (
                mapvot_seqno INTEGER PRIMARY KEY AUTOINCREMENT,
                mapvot_id INTEGER,
                mapvot_start INTEGER)
            ''')
            
            self.cursor.execute('''
                INSERT INTO temp_map_vote (mapvot_id, mapvot_start)
                SELECT mapvot_id, mapvot_start
                FROM map_vote
            ''')

            self.cursor.execute('DROP TABLE map_vote')

            self.cursor.execute('ALTER TABLE temp_map_vote RENAME TO map_vote')

            self.conn.commit()

    def create_Voter_Table(self):
        # Creates the table if it does not yet exist
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS voter (
            vot_seqno INTEGER PRIMARY KEY AUTOINCREMENT,
            vot_votmap_start INTEGER,
            vot_player TEXT,
            vot_dis_user_id INTEGER,                
            vot_map_name TEXT
        )
        ''')
        self.conn.commit()  

        self.ensure_column_exists ("voter", "vot_dis_user_id", "INTEGER")

    def create_Voter_Register_Table(self):
        # Creates the table if it does not yet exist
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS voter_register (
            votreg_seqno INTEGER PRIMARY KEY AUTOINCREMENT,
            votreg_dis_user TEXT,
            votreg_dis_user_id INTEGER UNIQUE,
            votreg_dis_nick TEXT,
            votreg_t17_id TEXT,
            votereg_ask_reg_cnt INTEGER,
            votereg_not_ingame_cnt INTEGER,
            votreg_clan_tag TEXT,
            votreg_t17_number TEXT,
            votreg_emojis TEXT,
            votreg_display_format TEXT                                                         
        )
        ''')
        self.conn.commit()  

        # Add new columns using existing helper method
        self.ensure_column_exists("voter_register", "votreg_clan_tag", "TEXT")
        self.ensure_column_exists("voter_register", "votreg_t17_number", "TEXT")
        self.ensure_column_exists("voter_register", "votreg_emojis", "TEXT")
        self.ensure_column_exists("voter_register", "votreg_display_format", "TEXT")

    def create_Balance_Table(self):
        # Creates the table if it does not yet exist
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS balance (
            bal_seqno INTEGER PRIMARY KEY AUTOINCREMENT,
            bal_limits TEXT,
            bal_allies TEXT,
            bal_axis TEXT,
            bal_datetime INTEGER
        )
        ''')

        self.conn.commit()  

    def create_Inappropriate_Name_Table(self):
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS inappropriate_name (
            inanme_seqno INTEGER PRIMARY KEY AUTOINCREMENT,
            inanme_player_id TEXT,
            inanme_name TEXT,
            inanme_message_id TEXT,
            inanme_decision TEXT,
            inanme_datetime INTERGER
        )
        ''')

        self.conn.commit()  

    def create_Key_Value(self):
        # Creates the table if it does not yet exist
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS key_value (
            keyval_seqno INTEGER PRIMARY KEY AUTOINCREMENT,
            keyval_key TEXT UNIQUE,
            keyval_value TEXT,
            keyval_datetime INTEGER
        )
        ''')

        self.conn.commit()  

    def column_exists(self, table_name, column_name):
        try:
            self.cursor.execute(f"PRAGMA table_info({table_name});")
            columns = [row[1] for row in self.cursor.fetchall()]

            if column_name not in columns:
                return False
            else:
                return True
        
        except sqlite3.OperationalError as e:
            print(f"Unexpected error: {e}")

    def ensure_column_exists(self, table_name, column_name, column_type):
       
        try:
            if not self.column_exists(table_name, column_name):
                self.cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type};")
                logger.info (f"Column '{column_name}' added in table '{table_name}'.")
            else:
                logger.debug(f"Column '{column_name}' already  exists in table '{table_name}'.")
        
        except sqlite3.OperationalError as e:
            print(f"Unexpected error: {e}")

    def select_Message_Id(self, sender):
        try:
            # Loads the message ID from the database
            self.cursor.execute('SELECT msg_id FROM messages WHERE msg_sender = (?) ORDER BY msg_seqno DESC LIMIT 1', (sender,))
            result = self.cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    def insert_Message_Id(self, sender, msg_id):
        try:
            # Insert the message ID in the database
            self.cursor.execute('INSERT INTO messages (msg_sender, msg_id, msg_datetime) VALUES (?, ?, ?)', (sender, str (msg_id), int(time.time())))
            self.conn.commit()  
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    def update_Message_Id(self, sender, msg_id):
        try:
            # Updates the message ID in the database for a specific sender
            logger.info ("msg_id: " + str (msg_id))
            self.cursor.execute('UPDATE messages SET msg_id = ?, msg_datetime = ? WHERE msg_sender = ?', (str (msg_id), int(time.time()), sender))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    def select_Key_Value(self, key):
        try:
            # Loads the key value from the database
            self.cursor.execute('SELECT keyval_value FROM key_value WHERE keyval_key = (?) ORDER BY keyval_seqno DESC LIMIT 1', (key,))
            result = self.cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    def insert_Key_Value(self, key, value):
        try:
            # Insert the key value in the database
            self.cursor.execute('INSERT INTO key_value (keyval_key, keyval_value, keyval_datetime) VALUES (?, ?, ?)', (key, value, int(time.time())))
            self.conn.commit()  
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    def update_Key_Value(self, key, value):
        try:
            # Updates the key value in the database for a specific key
            self.cursor.execute('UPDATE key_value SET keyval_value = ?, keyval_datetime = ? WHERE keyval_key = ?', (value, int(time.time()), key))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Unexpected error: {e}")   

    def insert_Inappropriate_Name(self, player_id, player_name, decision, msg_id):
        try:
            # Insert the message ID in the database
            self.cursor.execute(
                '''
                INSERT INTO inappropriate_name (inanme_player_id, inanme_name, inanme_message_id, inanme_decision, inanme_datetime) 
                VALUES (?, ?, ?, ?, ?)
                ''', 
                (player_id, player_name, str(msg_id), decision, int(time.time()))
            )
            self.conn.commit()  
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    def update_Inappropriate_Name(self, player_id, column, value):
        try:
            if column not in ['inanme_name', 'inanme_message_id', 'inanme_decision']:
                raise ValueError(f"Invalid column name: {column}")

            # perform update
            query = f"UPDATE inappropriate_name SET {column} = ? WHERE inanme_player_id = ?"
            self.cursor.execute(query, (value, player_id))
            self.conn.commit()

            logger.info (f"Updated {column} to {value} for inanme_player_id {player_id}")

        except ValueError as e:
            logger.error(f"ValueError: {e}")
        except sqlite3.OperationalError as e:
            logger.error(f"SQLite OperationalError: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    def select_Inappropriate_Name(self, player_id):
        try:
            self.cursor.execute(
                '''
                SELECT inanme_message_id, inanme_name, inanme_decision 
                FROM inappropriate_name 
                WHERE inanme_player_id = (?) 
                ORDER BY inanme_seqno DESC 
                LIMIT 1
                ''', 
                (player_id,)
            )
            result = self.cursor.fetchall()

            return result if result else None

        except Exception as e:
            logger.error(f"Error during SELECT operation: {e}")
            return None

    def insert_Balance(self, limits, allies, axis):
        try:
            # Insert the server balance in the database
            self.cursor.execute('INSERT INTO balance (bal_limits, bal_allies, bal_axis, bal_datetime) VALUES (?, ?, ?, ?)', (str (limits), str(allies), str(axis), int(time.time())))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    def insert_Map_Vote (self, msg_id, start):
        try:
            # Insert the message ID in the database
            self.cursor.execute('INSERT INTO map_vote (mapvot_id, mapvot_start) VALUES (?, ?)', (int (msg_id), int(start)))
            self.conn.commit()  

        except sqlite3.OperationalError as e:
            logger.error(f"SQLite OperationalError: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    def select_Last_Map_Vote(self, start):
        try:
            # Loads the message ID from the database
            self.cursor.execute('SELECT mapvot_id FROM map_vote WHERE mapvot_start = (?) ORDER BY mapvot_seqno DESC LIMIT 1', (int (start),))
            result = self.cursor.fetchone()
            return result[0] if result else None    

        except Exception as e:
            logger.error(f"Error during SELECT operation: {e}")
            return None

    def update_Map_Vote(self, start, column, value):
        try:
            if column not in ['mapvot_id', 'mapvot_start']:
                raise ValueError(f"Invalid column name: {column}")

            # perform update
            query = f"UPDATE map_vote SET {column} = ? WHERE mapvot_start = ?"
            self.cursor.execute(query, (value, start))
            self.conn.commit()

            logger.info (f"Updated {column} to {value} for mapvot_start {start}")

        except ValueError as e:
            logger.error(f"ValueError: {e}")
        except sqlite3.OperationalError as e:
            logger.error(f"SQLite OperationalError: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    def delete_Map_Vote(self, start):
        try:
            # Delete a vote
            self.cursor.execute("DELETE FROM map_vote WHERE mapvot_start = ?", (int (start),))
            self.conn.commit()

            logger.info (f"DELETE FROM map_vote WHERE mapvot_start = {int (start)}")

        except ValueError as e:
            logger.error(f"ValueError: {e}")
        except sqlite3.OperationalError as e:
            logger.error(f"SQLite OperationalError: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    def insert_Voter (self, start, player, discord_user_id, map_name):
        try:
            # Insert the message ID in the database
            self.cursor.execute('INSERT INTO voter (vot_votmap_start, vot_player, vot_dis_user_id, vot_map_name) VALUES (?, ?, ?, ?)', (int (start), player, discord_user_id, map_name))
            self.conn.commit()  

        except sqlite3.OperationalError as e:
            logger.error(f"SQLite OperationalError: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    def deleter_Voter (self, start, player, map_name):
        try:
            # Delete a vote
            self.cursor.execute("DELETE FROM voter WHERE vot_votmap_start = ? AND vot_player = ? AND vot_map_name = ?", (int (start), player, map_name))
            self.conn.commit()

        except sqlite3.OperationalError as e:
            logger.error(f"SQLite OperationalError: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    def deleter_all_Voter (self, start):
        try:
            # Delete a vote
            self.cursor.execute("DELETE FROM voter WHERE vot_votmap_start = ?", (int (start),))
            self.conn.commit()

        except sqlite3.OperationalError as e:
            logger.error(f"SQLite OperationalError: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    def insert_Voter_Registration(self, discord_user, discord_user_id, discord_nick, player_id, register_cnt, not_ingame_cnt, clan_tag=None, t17_number=None, emojis=None, display_format=None):
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                self.cursor.execute('INSERT INTO voter_register (votreg_dis_user, votreg_dis_user_id, votreg_dis_nick, votreg_t17_id, votereg_ask_reg_cnt, votereg_not_ingame_cnt, votreg_clan_tag, votreg_t17_number, votreg_emojis, votreg_display_format) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', 
                    (str(discord_user), int(discord_user_id), str(discord_nick), str(player_id), int(register_cnt), int(not_ingame_cnt), clan_tag, t17_number, emojis, display_format))
                self.conn.commit()
                return True

            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    if attempt < max_retries - 1:
                        logger.warning(f"Database locked, retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        continue
                logger.error(f"SQLite OperationalError after {max_retries} attempts: {e}")
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
            return False

    def select_T17_Voter_Registration(self, discord_user_id):
        try:
            self.cursor.execute('SELECT votreg_t17_id, votreg_clan_tag, votreg_t17_number, votreg_emojis FROM voter_register WHERE votreg_dis_user_id = (?) ORDER BY votreg_seqno DESC LIMIT 1', (int(discord_user_id),))
            result = self.cursor.fetchone()
            return result if result else None

        except sqlite3.OperationalError as e:
            logger.error(f"SQLite OperationalError: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    def select_T17_Voter (self, start_map):
        try:
            self.cursor.execute('select votreg_t17_id from voter, voter_register WHERE vot_dis_user_id = votreg_dis_user_id AND vot_votmap_start = (?);', (int (start_map),))
            result = self.cursor.fetchall()
            voters = [row[0] for row in result]

            return voters if voters else None

        except sqlite3.OperationalError as e:
            logger.error(f"SQLite OperationalError: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    def delete_T17_Voter_Registration(self, discord_user_id):
        """Delete a user's registration from the database."""
        try:
            self.cursor.execute(
                'DELETE FROM voter_register WHERE votreg_dis_user_id = ?',
                (int(discord_user_id),)
            )
            self.conn.commit()
            return True

        except sqlite3.OperationalError as e:
            logger.error(f"SQLite OperationalError: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False
