#!/bin/bash
# Скачиваем ffmpeg
wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
tar -xf ffmpeg-release-amd64-static.tar.xz
mv ffmpeg-*-static/ffmpeg ./ffmpeg
mv ffmpeg-*-static/ffprobe ./ffprobe
chmod +x ./ffmpeg ./ffprobe
rm -rf ffmpeg-*-static*
echo "✅ ffmpeg установлен локально"
pip install -r requirements.txt
echo "✅ Готово! Запускай: python bot.py"
