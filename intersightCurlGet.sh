#!/bin/bash
#Intersight CURL example

if [ "$#" -lt 4 ]; then
    echo -e "Intersight CURL Example\n"
    echo -e "Usage: ./script.sh 'API Key ID' 'API Secretkey Filename' 'HTTP method [GET/POST/DELETE]' 'API Endpoint' 'Payload [Required only for POST]\n"
    echo -e "Example GET: ./script.sh '1111/2222/3333' 'SecretKey.txt' 'GET' '/api/v1/compute/PhysicalSummaries?\$top=1&\$select=Serial'\n"
    echo -e "Example DELETE: ./script.sh '1111/2222/3333' 'SecretKey.txt' 'DELETE' '/api/v1/vnic/LanConnectivityPolicies/60bfd0964fa6a1d629e66eb6'\n"
    echo -e "Example POST: ./script.sh '1111/2222/3333' 'SecretKey.txt' 'POST' '/api/v1/ntp/Policies' '{"Organization":{"ObjectType":"organization.Organization","Moid":"5ddea34a6972652d3353b462"},"Name":"myNtpPolicy","Enabled":true,"NtpServers":["1.1.1.1"]}'"
    exit 2
fi

hostName="intersight.com"
apiKey=$1
apiSecretKey=$2
method=${3^^}
url=$4
payload=$5

apiTime="date: "$(date -u '+%a, %d %b %Y %T %Z')

#SHA256 digest of HTTP payload
apibodyDigest="digest: SHA-256="$(printf ''$payload'' | openssl dgst -sha256 -binary | base64)

#SHA256 digest of headers signed by private key file, header info must be in lower case for the digest
apiSignature=$(
printf "(request-target): %s %s
%s
%s
host: %s" "${method,,}" "${url,,}" "$apiTime" "$apibodyDigest" "$hostName" | openssl dgst -sha256 -binary -sign $2 | base64 -w 0)


if [ $method = "POST" ]
then
curl -X $method "https://"$hostName$url \
-H 'Accept: "application/json"' \
-H 'Content-Type: application/json' \
-H 'Host: '$hostName -H "$apiTime" -H "$apibodyDigest" \
-H 'Authorization: Signature keyId="'"$apiKey"'",algorithm="rsa-sha256",headers="(request-target) date digest host",signature="'"$apiSignature"'"' \
-d $payload
elif [ $method = "GET" ] || [ $method = "DELETE" ]
then
curl -X $method "https://"$hostName$url \
-H 'Accept: "application/json"' \
-H 'Host: '$hostName -H "$apiTime" -H "$apibodyDigest" \
-H 'Authorization: Signature keyId="'"$apiKey"'",algorithm="rsa-sha256",headers="(request-target) date digest host",signature="'"$apiSignature"'"'
fi