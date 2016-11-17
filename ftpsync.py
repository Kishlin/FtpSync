#!/usr/bin/python
# -*- coding: UTF-8 -*-

import os
import time
import logging.config
import argparse
from ftplib import FTP


def ftp_make_dir(ftp, dir_name, logger):
    wd = ftp.pwd()
    dirs_list = dir_name.split('/')
    for folder in dirs_list:
        if folder not in ftp.nlst():
            try:
                ftp.mkd(folder)
            except:
                logger.debug('Could not create {0}.'.format(folder))
        ftp.cwd(folder)
    ftp.cwd(wd)


def ftp_rm_tree(ftp, path, logger):
    wd = ftp.pwd()
    try:
        names = ftp.nlst(path)
    except:
        return
    for name in names:
        if os.path.split(name)[1] in ('.', '..'): continue
        try:
            ftp.cwd(name)
            ftp.cwd(wd)
            ftp_rm_tree(ftp, name, logger)
        except:
            ftp.delete(name)
    try:
        ftp.rmd(path)
        logger.info("The folder {0} has been deleted.".format(path))
    except:
        return


def ftp_add_file(ftp, name, local_file, logger):
    try:
        file = open(local_file, 'rb')
        ftp.storbinary('STOR {0}'.format(name), file)
        file.close()
    except IOError:
        logger.debug('Could not open local file {0}.'.format(local_file))
    except:
        logger.debug('Could not upload file {0}.'.format(name))


def ftp_delete_file(ftp, name, logger):
    try:
        ftp.delete(name)
    except:
        logger.debug('Could not delete file {0}. Maybe it was in a directory deleted beforehand?'.format(name))


def ftp_edit_file(ftp, name, local_file, logger):
    ftp_delete_file(ftp, name, logger)
    ftp_add_file(ftp, name, local_file, logger)


def ftp_move_file(ftp, old_name, new_name, logger):
    try:
        ftp.rename(old_name, new_name)
    except:
        logger.debug('Could not move file from {0} to {1}. Maybe it was moved with its parent directory beforehand?'.format(old_name, new_name))


def folder_added(name, logger, ftp, ref_directory):
    ftp_make_dir(ftp, name[len(ref_directory) + 1:], logger)
    logger.info('The folder {0} has been created.'.format(name))


def folder_deleted(name, logger, ftp, ref_directory):
    ftp_rm_tree(ftp, name[len(ref_directory) + 1:], logger)
    logger.info('The folder {0} has been deleted.'.format(name))


def folder_moved(old_name, new_name, logger, ftp, ref_directory):
    ftp_rm_tree(ftp, old_name[len(ref_directory) + 1:], logger)
    ftp_make_dir(ftp, new_name[len(ref_directory) + 1:], logger)
    new_folder = ({}, {})
    fill_directories_dictionary(new_folder[0], new_folder[1], new_name)
    for path in new_folder[0].values():
        ftp_make_dir(ftp, path[len(ref_directory) + 1:], logger)
    for file in new_folder[1].values():
        logger.info('Trying to add file {0}...'.format(file))
        ftp_add_file(ftp, file[0][len(ref_directory) + 1:], file[0], logger)
    logger.info('The folder {0} was moved to {1}.'.format(old_name, new_name))


def file_modified(name, logger, ftp, ref_directory):
    ftp_edit_file(ftp, name[len(ref_directory) + 1:], name, logger)
    logger.info('The file {0} has been modified.'.format(name))


def file_added(name, logger, ftp, ref_directory):
    ftp_add_file(ftp, name[len(ref_directory) + 1:], name, logger)
    logger.info('The file {0} has been created.'.format(name))


def file_deleted(name, logger, ftp, ref_directory):
    ftp_delete_file(ftp, name[len(ref_directory) + 1:], logger)
    logger.info('The file {0} has been deleted.'.format(name))


def file_moved(old_name, new_name, logger, ftp, ref_directory):
    ftp_move_file(ftp, old_name[len(ref_directory) + 1:], new_name[len(ref_directory) + 1:], logger)
    logger.info("The  file  {0} has been moved to {1}.".format(old_name, new_name))


def folder_analyse(old_state, new_state, logger, ftp, ref_directory):
    for node in new_state.keys():
        if node in old_state.keys():
            old_name = old_state[node]
            new_name = new_state[node]
            if old_name != new_name:
                folder_moved(old_name, new_name, logger, ftp, ref_directory)
        else:
            folder_added(new_state[node], logger, ftp, ref_directory)
    for node in old_state.keys():
        if node not in new_state.keys():
            folder_deleted(old_state[node], logger, ftp, ref_directory)


def files_analyse(old_state, new_state, logger, ftp, ref_directory):
    for node in new_state.keys():
        if node in old_state.keys():
            old_name = old_state[node][0]
            new_name = new_state[node][0]
            if new_name == old_name:
                old_time = old_state[node][1]
                new_time = new_state[node][1]
                if old_time != new_time:
                    file_modified(new_name, logger, ftp, ref_directory)
            else:
                file_moved(old_name, new_name, logger, ftp, ref_directory)
        else:
            file_added(new_state[node][0], logger, ftp, ref_directory)
    for node in old_state.keys():
        if node not in new_state.keys():
            file_deleted(old_state[node][0], logger, ftp, ref_directory)


def fill_files_dictionary(dictionary, folder, files):
    for file in files:
        full_path = os.path.join(folder, file)
        # Récupération du timestamp de dernière modification
        timestamp = int(os.path.getmtime(full_path))
        inode = int(os.stat(full_path).st_ino)
        dictionary[inode] = (full_path, timestamp)


def fill_directories_dictionary(dictionary_folders, dictionary_files, folder):
    for root, dirs, files in os.walk(folder):
        fill_files_dictionary(dictionary_files, root, files)
        inode = int(os.stat(root).st_ino)
        dictionary_folders[inode] = root


def run(args, logger, ftp):
    old_state = ({}, {})
    fill_directories_dictionary(old_state[0], old_state[1], args.directory)
    while 1 == 1:
        time.sleep(args.time)
        new_state = ({}, {})
        fill_directories_dictionary(new_state[0], new_state[1], args.directory)
        folder_analyse(old_state[0], new_state[0], logger, ftp, args.directory)
        files_analyse(old_state[1], new_state[1], logger, ftp, args.directory)
        old_state = new_state


def parse_arguments():
    parser = argparse.ArgumentParser(prog='FtpSync',
                                     description='This program will let you sync a folder with a ftp server.')
    parser.add_argument('-d', '--directory', help='The directory you want to supervise', type=str)
    parser.add_argument('-l', '--log', help='The config file for the logger.', type=str)
    parser.add_argument('-t', '--time', help='Frequency of folder check (in seconds).', type=int, default=1)
    return parser.parse_args()


def check_arguments(args):
    check = True
    if not os.path.isdir(args.directory):
        print('Error : The directory you want to supervise does not exist.')
        check = False
    if not os.path.exists(args.log) or os.path.isdir(args.log):
        print('Error : The config file for the logger does not exist.')
        check = False
    if args.time <= 0:
        print('You cannot specify a frequency inferior or equal to 0.')
        check = False
    return check


def init_log_file(log_file):
    logging.config.fileConfig(log_file)
    return logging.getLogger("main")


def init_ftp(hostname, user, password, remote_dir):
    ftp = FTP(hostname)
    ftp.login(user, password)
    ftp.cwd(remote_dir)
    return ftp


def main():
    args = parse_arguments()
    if check_arguments(args):
        logger = init_log_file(args.log)
        ftp = init_ftp("localhost", "sammy", "user", "files")
        logger.info(ftp.getwelcome())
        run(args, logger, ftp)
        ftp.quit()


main()
