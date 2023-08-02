#!/bin/sh
# shellcheck disable=SC3010,SC2145,SC3045

set -euf

if [ -z "${TERM-}" ]; then
    echo 'no TERM var, assuming sane default'
    tput='tput -T xterm-256color'
else
    tput='tput'
fi

red=$($tput setaf 1)
green=$($tput setaf 2)
blue=$($tput setaf 4)
white=$($tput setaf 7)
bold=$($tput bold)
reset=$($tput sgr0)

info() {
    echo "${bold}${white}━━┫${blue}${@}${white}┣━━${reset}"
}

success() {
    echo "${bold}${white}━━┫${green}${@}${white}┣━━${reset}"
}

warn() {
    echo "${bold}${red}!! ${white}${@}${reset}"
}

if [[ $# -eq 1 ]]; then
    if [ "$1" = "-h" ] || [ "$1" = "--help" ] || [ "$1" = "help" ]; then
        echo "flags -u [db uri] -f [filename]"
    else
        echo "please use flags to pass args to this script (-h --help for help)"
    fi
    warn "Exiting"
    exit 0
fi

while getopts u:f: flag; do
    case "${flag}" in
    u) _db_uri=${OPTARG} ;;
    f) _filename=${OPTARG} ;;
    *)
        warn "invalid flags, allowed -u [db uri] -f [filename]"
        warn "Exiting"
        exit
        ;;
    esac
done

if [[ -z "${VIRTUAL_ENV+set}" ]]; then
    warn "Please run this script with pipenv run ./generate_sql_template.sh or from within a pipenv shell"
    warn "Exiting"
    exit 0
fi

if [[ -n "${_db_uri+set}" ]]; then
    info "using provided db uri"
    db_uri="$_db_uri"

elif [[ -n "${HERMES_DATABASE_URL+set}" ]]; then
    db_uri=${HERMES_DATABASE_URL}_template
    info "using HERMES_DATABASE_URL uri + _template"

fi

if [[ -n "${db_uri+set}" ]]; then
    data=$(echo "$db_uri" | cut -d "/" -f 3)
    username=$(echo "$data" | cut -d "@" -f 1 | cut -d ":" -f 1)
    password=$(echo "$data" | cut -d "@" -f 1 | cut -d ":" -f 2)
    host=$(echo "$data" | cut -d "@" -f 2 | cut -d "/" -f 1 | cut -d ":" -f 1)
    port=$(echo "$data" | cut -d "@" -f 2 | cut -d "/" -f 1 | cut -d ":" -f 2)
    db_name=$(echo "$db_uri" | cut -d "/" -f 4)

else
    info "trying to build from env vars"
    if [[ -n "${HERMES_DATABASE_USER+set}" ]]; then
        username=$HERMES_DATABASE_USER
    else
        username="postgres"
    fi

    if [[ -n "${HERMES_DATABASE_PASS+set}" ]]; then
        password=$HERMES_DATABASE_PASS
    else
        password=""
    fi

    if [[ -n "${HERMES_DATABASE_HOST+set}" ]]; then
        host=$HERMES_DATABASE_HOST
    else
        host="127.0.0.1"
    fi

    if [[ -n "${HERMES_DATABASE_PORT+set}" ]]; then
        port=$HERMES_DATABASE_PORT
    else
        port=5432
    fi

    if [[ -n "${HERMES_DATABASE_NAME+set}" ]]; then
        db_name=${HERMES_DATABASE_NAME}_template
    else
        db_name="hermes_template"
    fi

    db_uri="postgres+psycopg2://${username}:${password}@${host}:${port}/${db_name}"
fi

if [[ -n "${_filename+set}" ]]; then
    filename=$_filename
else
    filename="hermes_template.sql"
fi

info This script is meant to be run inside the Hermes pipenv virtual env
info Collected values:
echo db uri: "$db_uri"
echo username: "$username"
echo password: "$password"
echo host: "$host"
echo port: "$port"
echo db_name: "$db_name"

echo filename: "$filename"

read -rp "Proceed (y/n)? " confirm

if [[ "$confirm" != "y" ]]; then
    echo "use the -u flag to provide a custom db uri"
    warn "Exiting"
    exit 0
fi

export HERMES_DATABASE_URL="$db_uri"
export PGPASSWORD="$password"

info "dropping and recreating database ${db_name}"
psql -U "$username" -h "$host" -p "$port" -c "DROP DATABASE IF EXISTS ${db_name};"
psql -U "$username" -h "$host" -p "$port" -c "CREATE DATABASE ${db_name};"

info "running migrations"
python -m manage migrate

info "dumping database schema into '$filename'"
pg_dump -s -U "$username" -h "$host" -p "$port" -d "$db_name" >"$filename"

info "dropping database ${db_name}"
psql -U "$username" -h "$host" -p "$port" -c "DROP DATABASE ${db_name};"

success "completed"
