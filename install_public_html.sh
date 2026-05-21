#!/bin/sh

cd "$(dirname "$0")"
ENV_NAME="$(basename $(pwd))"

echo "Installing $(realpath ./public_html) to $(realpath ~/public_html) with ENV_NAME=$ENV_NAME..."
mkdir -p ~/public_html/cgi-bin/
chmod 755 ~/public_html/
chmod 755 ~/public_html/cgi-bin/

rm -rf ~/public_html/$ENV_NAME
cp -r ./public_html/ONIDbot ~/public_html/$ENV_NAME

rm -rf ~/public_html/cgi-bin/$ENV_NAME
cp -r ./public_html/cgi-bin/ONIDbot ~/public_html/cgi-bin/$ENV_NAME
echo "Done!"
