#!/usr/bin/python
# -*- coding: UTF-8 -*-

import re
import os
import time
import logging.config
import argparse
from ftplib import FTP


def ftp_make_dir(ftp, dir_name, logger):
    """
    Crée un dossier sur le ftp.

    :param ftp: Serveur ftp.
    :param dir_name: Nom du dossier à créer.
    :param logger: Logger pour l'enregistrement des logs.
    """
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
    """
    Supprime récursivement un dossier et son contenu sur le ftp.

    :param ftp: Serveur ftp.
    :param path:  Nom du dossier à supprimer.
    :param logger: Logger pour l'enregistrement des logs.
    :return:
    """
    wd = ftp.pwd()
    try:
        names = ftp.nlst(path)
    except:
        return
    # Pour chaque fichier ou dossier contenu dans le dossier courant du ftp.
    for name in names:
        if os.path.split(name)[1] in ('.', '..'): continue
        try:
            # Si on peut s'y déplacer, c'est un dossier -> on revient au dossier de base sur le ftp
            # puis lance la méthode récursivement sur le dossier en question
            ftp.cwd(name)
            ftp.cwd(wd)
            ftp_rm_tree(ftp, name, logger)
        except:
            # Si c'est un fichier il n'y a qu'à le supprimer.
            ftp.delete(name)
    try:
        ftp.rmd(path)
        logger.info("The folder {0} has been deleted.".format(path))
    except:
        return


def ftp_add_file(ftp, name, local_file, logger):
    """
    Ajoute un fichier sur le serveur FTP en y inscrivant le contenu du fichier local.

    :param ftp: Serveur FTP.
    :param name: Chemin relatif du fichier à créer sur le ftp, depuis le dossier de base.
    :param local_file: Chemin local du fichier (relatif ou absolu)
    :param logger: Logger pour l'enregistrement des logs.
    """
    try:
        file = open(local_file, 'rb')
        ftp.storbinary('STOR {0}'.format(name), file)
        file.close()
    except IOError:
        logger.debug('Could not open local file {0}.'.format(local_file))
    except:
        logger.debug('Could not upload file {0}.'.format(name))


def ftp_delete_file(ftp, name, logger):
    """
    Supprime un fichier sur le serveur FTP.

    :param ftp: Serveur FTP.
    :param name: Chemin relatif du fichier à supprimer sur le ftp, depuis le dossier de base.
    :param logger: Logger pour l'enregistrement des logs.
    """
    try:
        ftp.delete(name)
    except:
        logger.debug('Could not delete file {0}. Maybe it was in a directory deleted beforehand?'.format(name))


def ftp_edit_file(ftp, name, local_file, logger):
    """
    Modifie un fichier sur le serveur FTP pour y inscrire le nouveau contenu du fichier local.

    :param ftp: Serveur FTP.
    :param name: Chemin relatif du fichier sur le FTP depuis le dossier de base.
    :param local_file: Chemin relatif ou absolu du fichier local.
    :param logger: Logger pour l'enregistrement des logs.
    """
    ftp_delete_file(ftp, name, logger)
    ftp_add_file(ftp, name, local_file, logger)


def ftp_move_file(ftp, old_name, new_name, logger):
    """
    Déplace un fichier sur le serveur FTP.

    :param ftp: Serveur FTP.
    :param old_name: Ancien nom du fichier.
    :param new_name: Nouveau nom du fichier.
    :param logger: Logger pour l'enregistrement des logs.
    """
    try:
        ftp.rename(old_name, new_name)
    except:
        logger.debug('Could not move file from {0} to {1}. Maybe it was moved with its parent directory beforehand?'.format(old_name, new_name))


def folder_added(name, logger, ftp, ref_directory):
    """
    Lance l'ajout d'un dossier sur le ftp.

    :param name: Nom relatif ou absolu du dossier à ajouter.
    :param logger: Logger pour l'enregistrement des logs.
    :param ftp: Serveur FTP.
    :param ref_directory: Répertoire de référence.
    """
    ftp_make_dir(ftp, name[len(ref_directory) + 1:], logger)
    logger.info('The folder {0} has been created.'.format(name))


def folder_deleted(name, logger, ftp, ref_directory):
    """
    Lance la suppression d'un dossier sur le FTP.

    :param name: Nom relatif ou absolu du dossier à supprimer.
    :param logger: Logger pour l'enregistrement des logs.
    :param ftp: Serveur FTP.
    :param ref_directory: Répertoire de référence.
    """
    ftp_rm_tree(ftp, name[len(ref_directory) + 1:], logger)
    logger.info('The folder {0} has been deleted.'.format(name))


def folder_moved(old_name, new_name, logger, ftp, ref_directory):
    """
    Lance le déplacement d'un dossier sur le FTP.

    :param old_name: Ancien nom relatif ou absolu du dossier.
    :param new_name: Nouveau nom relatif ou absolu du dossier.
    :param logger: Logger pour l'enregistrement des logs.
    :param ftp: Serveur FTP.
    :param ref_directory: Répertoire de référence.
    """
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
    """
    Lance la modification d'un fichier sur le serveur FTP.

    :param name: Nom relatif ou absolu du fichier.
    :param logger: Logger pour l'enregistrement des logs.
    :param ftp: Serveur FTP.
    :param ref_directory: Répertoire de référence.
    """
    ftp_edit_file(ftp, name[len(ref_directory) + 1:], name, logger)
    logger.info('The file {0} has been modified.'.format(name))


def file_added(name, logger, ftp, ref_directory):
    """
    Lance l'ajout d'un fichier sur le serveur FTP.

    :param name: Nom relatif ou absolu du fichier.
    :param logger: Logger pour l'enregistrement des logs.
    :param ftp: Serveur FTP.
    :param ref_directory: Répertoire de référence.
    """
    ftp_add_file(ftp, name[len(ref_directory) + 1:], name, logger)
    logger.info('The file {0} has been created.'.format(name))


def file_deleted(name, logger, ftp, ref_directory):
    """
    Lance la suppression d'un fichier sur le serveur FTP.

    :param name: Nom relatif ou absolu du fichier à supprimer.
    :param logger: Logger pour l'enregistrement des logs.
    :param ftp: Serveur FTP.
    :param ref_directory: Répertoire de référence.
    """
    ftp_delete_file(ftp, name[len(ref_directory) + 1:], logger)
    logger.info('The file {0} has been deleted.'.format(name))


def file_moved(old_name, new_name, logger, ftp, ref_directory):
    """
    Lance le déplacement d'un fichier sur le serveur FTP.

    :param old_name: Ancien nom relatif ou absolu du fichier.
    :param new_name: Nouveau nom relatif ou absolu du fichier.
    :param logger: Logger pour l'enregistrement des logs.
    :param ftp: Serveur FTP.
    :param ref_directory: Répertoire de référence.
    """
    ftp_move_file(ftp, old_name[len(ref_directory) + 1:], new_name[len(ref_directory) + 1:], logger)
    logger.info("The  file  {0} has been moved to {1}.".format(old_name, new_name))


def folder_analyse(old_state, new_state, logger, ftp, ref_directory):
    """
    Analyse les deux dictionnaires de dossiers en comparant les entrées.

    :param old_state: Dictionnaire d'ancien état.
    :param new_state: Dictionnaire de nouvel état.
    :param logger: Logger pour l'enregistrement des logs.
    :param ftp: Serveur FTP.
    :param ref_directory: Répertoire de référence.
    """
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
    """
    Analyse les deux dictionnaires de fichiers en comparant les entrées.

    :param old_state: Dictionnaire d'ancien état.
    :param new_state: Dictionnaire de nouvel état.
    :param logger: Logger pour l'enregistrement des logs.
    :param ftp: Serveur FTP.
    :param ref_directory: Répertoire de référence.
    """
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
    """
    Remplie le dictionaire de fichiers à partir d'une liste de fichiers dans un répertoire donné.

    :param dictionary: Le dictionnaire à remplire.
    :param folder: Le dossier dont il faut lister le contenu.
    :param files: Les fichiers à intégrer dans le dictionnaire.
    """
    for file in files:
        full_path = os.path.join(folder, file)
        # Récupération du timestamp de dernière modification
        timestamp = int(os.path.getmtime(full_path))
        inode = int(os.stat(full_path).st_ino)
        dictionary[inode] = (full_path, timestamp)


def fill_directories_dictionary(dictionary_folders, dictionary_files, folder):
    """
    Remplie deux dictionnaires de dossiers et fichiers à partir d'un dossier racine.

    :param dictionary_folders: Dictionnaire de dossiers.
    :param dictionary_files: Dictionnaire de fichiers.
    :param folder: Dossier racine dont on veut lister le contenu.
    """
    for root, dirs, files in os.walk(folder):
        fill_files_dictionary(dictionary_files, root, files)
        inode = int(os.stat(root).st_ino)
        dictionary_folders[inode] = root


def run(args, logger, ftp):
    """
    Procède à la synchronisation.

    :param args: Les arguments rentrés par l'utilisateur
    :param logger: Logger pour l'enregistrement des logs.
    :param ftp: Serveur FTP.
    """
    old_state = ({}, {})
    fill_directories_dictionary(old_state[0], old_state[1], args.directory)
    while 1 == 1:
        time.sleep(args.time)
        new_state = ({}, {})
        fill_directories_dictionary(new_state[0], new_state[1], args.directory)
        folder_analyse(old_state[0], new_state[0], logger, ftp, args.directory)
        files_analyse(old_state[1], new_state[1], logger, ftp, args.directory)
        old_state = new_state


def parse_arguments() :
    """
    S'occupe du parsing des arguments rentrés par l'utilisateurs.

    :return: Arguments.
    """
    parser = argparse.ArgumentParser(prog='FtpSync', description='This program will let sync a folder with a ftp server.')
    parser.add_argument('-d', '--directory', help='The name of the local folder you want to synchronize with the ftp.', type=str)
    parser.add_argument('-f', '--ftp', help="The ftp host name, user name, and password, separated with ':'.", type=str)
    parser.add_argument('-r', '--remote', help='The name of the folder on ftp you want to synchronize with the local folder.', type=str)
    parser.add_argument('-l', '--logs', help='The config file for the logger.', type=str)
    parser.add_argument('-L', '--logger', help='Name of the logger you want to use.', type=str, default="main")
    parser.add_argument('-t', '--time', help='Frequency of the folder check (in seconds).', type=int, default=1)
    return parser.parse_args()


def check_arguments(args) :
    """
    Vérifie la validité des arguments rentrés. Si au moins un argument n'est pas valide, renvoie faux. Vrai sinon.

    :param args: Arguments.
    :return: Validité des arguments.
    """
    check = True
    if args.ftp is None:
        print('Error : The FTP logs have not been specified.')
        check = False
    else:
        pattern = re.compile("^([\w\d\.]+:){2}([\w\d\.]+)$")
        if not pattern.match(args.ftp):
            print('Error : The FTP logs do not match the expected format.')
            check = False
    if args.directory is None or not os.path.isdir(args.directory):
        print('Error : The directory you want to supervise does not exist.')
        check = False
    if args.remote is None:
        print('Error : the ftp folder has not been specified.')
        check = False
    if args.logs is None or not os.path.exists(args.logs):
        print('Error : The config file for the logger does not exist.')
        check = False
    if args.time <= 0 :
        print('You cannot specify a frequency inferior or equal to 0.')
        check = False
    return check


def init_log_file(log_file, logger_name):
    """
    Initialise le logger à partir d'un fichier de configuration, et d'un nom de logger à utiliser.

    :param log_file: Fichier de configuration des loggers.
    :param logger_name: Loggeur à utiliser.
    :return:
    """
    logging.config.fileConfig(log_file)
    return logging.getLogger(logger_name)


def init_ftp(ftp_details, remote_dir, logger):
    """
    Initialise la connexion FTP, et se place dans le dossier à synchroniser avec le répertoire local.

    :param ftp_details: Details du ftp sous la forme hostname:user:password
    :param remote_dir: Nom du dossier de base.
    :param logger: Logger pour l'enregistrement des logs.
    :return:
    """
    try:
        logs = ftp_details.split(':')
        ftp = FTP(logs[0])
        ftp.login(logs[1], logs[2])
        logger.info(ftp.getwelcome())
        ftp.cwd(remote_dir)
        return ftp
    except:
        logger.error('Could not connect to the ftp. Are you sure the credentials are correct?')


def main():
    """
    Méthode principale. Procède au parsing des logs, l'initialisation du logger et du ftp, puis à la synchronisation.
    """
    args = parse_arguments()
    if check_arguments(args):
        logger = init_log_file(args.logs, args.logger)
        ftp = init_ftp(args.ftp, args.remote, logger)
        if ftp is not None:
            run(args, logger, ftp)
            ftp.quit()


main()
