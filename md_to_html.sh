#!/bin/sh

cat <<EOF > ./public_html/ONIDbot/index.html
<!DOCTYPE html>
<html lang="en">

<head>
	<link rel="icon" type="image/x-icon" href="./assets/favicon.ico">
	<link rel="apple-touch-icon" sizes="180x180" href="./assets/icon_180x180.png">
	<link rel="icon" type="image/png" sizes="512x512" href="./assets/icon_512x512.png">
	<link rel="icon" type="image/png" sizes="192x192" href="./assets/icon_192x192.png">
	<link rel="icon" type="image/png" sizes="180x180" href="./assets/icon_180x180.png">
	<link rel="icon" type="image/png" sizes="32x32" href="./assets/icon_32x32.png">
	<link rel="icon" type="image/png" sizes="16x16" href="./assets/icon_16x16.png">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
	<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.8.1/github-markdown-dark.min.css" />
	<style>
		.markdown-body {
			box-sizing: border-box;
			min-width: 200px;
			max-width: 980px;
			margin: 0 auto;
			padding: 45px;
		}
		@media (max-width: 767px) {
			.markdown-body {
				padding: 15px;
			}
		}
	</style>
	<title>ONIDbot - Home</title>
</head>

<body class="markdown-body">
EOF

cmark-gfm ./README.md >> ./public_html/ONIDbot/index.html

cat <<EOF >> ./public_html/ONIDbot/index.html
</body>

</html>
EOF

echo "Done!"
