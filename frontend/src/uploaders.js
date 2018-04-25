const uploaders = {};

uploaders.elixireManager = token => `#!/bin/bash
# https://gitlab.com/elixire/elixiremanager
# based on https://github.com/aveao/ownshot
# based on https://github.com/jomo/imgur-screenshot

current_version="v5.0.0"

############# BASIC CONFIG #############

apiurl="${
  window.client.endpoint
}" # example: https://elixi.re/api (no slash on end!)
apikey="${token}" # API key, which you can get from elixire web ui
open="false" # Open the link? true/false
edit="false" # Edit before uploading? true/false
mode="select" # What should be captured? select/window/full
copy_url="true" # Copy URL after upload? true/false
keep_file="false" # Keep image after uploading? true/false
file_dir="\${HOME}/Pictures" # Location for images to be saved.

########### END BASIC CONFIG ###########

########### ADVANCED CONFIG ############

is_admin="${
  window.client.profile.admin ? "?admin=1" : ""
}" # This is sort of lazy. If you're an admin, put ?admin=1, if you're not, keep it empty

file_name_format="elixire-%Y_%m_%d-%H:%M:%S.png"

edit_command="gimp %img"

log_file="\${HOME}/.elixireuploader.log"
icon_path="\${HOME}/Pictures/.elixireicon.png"

upload_connect_timeout="5"
upload_timeout="120"
upload_retries="1"

screenshot_select_command="maim -u -s %img"
screenshot_window_command="maim -u %img"
screenshot_full_command="maim -u %img"
open_command="xdg-open %url"

########## END ADVANCED CONFIG ##########

# dependency check
if [ "\${1}" = "--check" ]; then
  (which grep &>/dev/null && echo "OK: found grep") || echo "ERROR: grep not found"
  (which jq &>/dev/null && echo "OK: found jq") || echo "ERROR: jq not found"
  (which notify-send &>/dev/null && echo "OK: found notify-send") || echo "ERROR: notify-send (from libnotify-bin) not found"
  (which maim &>/dev/null && echo "OK: found maim") || echo "ERROR: maim not found"
  (which slop &>/dev/null && echo "OK: found slop") || echo "ERROR: slop not found"
  (which xclip &>/dev/null && echo "OK: found xclip") || echo "ERROR: xclip not found"
  (which convert &>/dev/null && echo "OK: found imagemagick") || echo "ERROR: imagemagick not found"
  (which curl &>/dev/null && echo "OK: found curl") || echo "ERROR: curl not found"
  exit 0
fi


# notify <'ok'|'error'> <title> <text>
function notify() {
  if [ -f \$icon_path ];
    then
    echo "icon exists, moving on"
    # icon already exists
  else
    echo "Downloading icon"
    wget "https://elixi.re/i/csn.png" --output-document=\$icon_path
  fi

  if [ "\${1}" = "error" ]; then
    notify-send -a elixiremanager -u critical -c "im.error" -i "\${icon_path}" -t 5000 "elixiremanager: \${2}" "\${3}"
  else
    notify-send -a elixiremanager -u low -c "transfer.complete" -i "/tmp/thumb.png" -t 5000 "elixiremanager: \${2}" "\${3}"
  fi
}

function take_screenshot() {
  echo "Please select area"
  sleep 0.1 # https://bbs.archlinux.org/viewtopic.php?pid=1246173#p1246173

  cmd="screenshot_\${mode}_command"
  cmd=\${!cmd//\%img/\${1}}

  shot_err="\$(\${cmd} &>/dev/null)" #takes a screenshot with selection
  if [ "\${?}" != "0" ]; then
    echo "Failed to take screenshot '\${1}': '\${shot_err}'. For more information visit https://github.com/jomo/imgur-screenshot/wiki/Troubleshooting" | tee -a "\${log_file}" #didn't change link as their troubleshoot likely helps more
    notify error "Something went wrong :(" "Information has been logged"
    exit 1
  fi
  convert -thumbnail 150 \${1} /tmp/thumb.png
}

function shorten_link() {
  url="\${apiurl}/shorten\${is_admin}"
  echo "Shortening '\${1}' on '\${url}'..."
  response="\$(curl --compressed --connect-timeout "\${upload_connect_timeout}" -m "\${upload_timeout}" --retry "\${upload_retries}" -H "Authorization: \${apikey}" -H "Content-Type: application/json" -X POST -d "{\"url\":\"\${1}\"}" \${url} | jq .url -r)"
  
  handle_upload_success \$response "\${1}"
}

function upload_file() {
  url="\${apiurl}/upload\${is_admin}"
  echo "Uploading '\${1}' to '\${url}'..."
  response="\$(curl --compressed --connect-timeout "\${upload_connect_timeout}" -m "\${upload_timeout}" --retry "\${upload_retries}" -H "Authorization: \${apikey}" -F upload=@\${1} \${url} | jq .url -r)"

  handle_upload_success \$response "\${1}"
}

function handle_upload_success() {
  echo ""
  echo "result link: \${1}"

  if [ "\${copy_url}" = "true" ]; then
    echo -n "\${1}" | xclip -selection clipboard
    echo "URL copied to clipboard"
  fi

  # print to log file: image link, image location, delete link
  echo -e "\${1}\t\${2}" >> "\${log_file}"

  notify ok "Success!" "\${1}"

  if [ ! -z "\${open_command}" ] && [ "\${open}" = "true" ]; then
    open_cmd=\${open_command//\%url/\${1}}
    open_cmd=\${open_cmd//\%img/\${2}}
    echo "Opening '\${open_cmd}'"
    eval "\${open_cmd}"
  fi
}

function handle_upload_error() {
  error="Upload failed: \"\${1}\""
  echo "\${error}"
  echo -e "Error\t\${2}\t\${error}" >> "\${log_file}"
  notify error "Upload failed :(" "\${1}"
}

while [ \${#} != 0 ]; do
  case "\${1}" in
    -h | --help)
echo "usage: \${0} [-c | --check | -v | -h]"
echo "       \${0} [option]... [file]..."
echo ""
echo "  -h, --help                   Show this help, exit"
echo "  -v, --version                Show current version, exit"
echo "      --check                  Check if all dependencies are installed, exit"
echo "  -sh, --shorten <url>         Shortens a url, copies result"
echo "  -o, --open <true|false>      Override 'open' config"
echo "  -s, --select                 Override 'mode' config to select a screen area"
echo "  -w, --window                 Override 'mode' config to upload the whole window"
echo "  -f, --full                   Override 'mode' config to upload the full screen"
echo "  -e, --edit <true|false>      Override 'edit' config"
echo "  -i, --edit-command <command> Override 'edit_command' config (include '%img'), sets --edit 'true'"
echo "  -k, --keep-file <true|false> Override 'keep_file' config"
echo "  file                         Upload file instead of taking a screenshot"
exit 0;;
-v | --version)
echo "\${current_version}"
exit 0;;
-sh | --shorten)
shorten_link "\${2}"
exit 0;;
-s | --select)
mode="select"
shift;;
-w | --window)
mode="window"
shift;;
-f | --full)
mode="full"
shift;;
-o | --open)
open="\${2}"
shift 2;;
-e | --edit)
edit="\${2}"
shift 2;;
-i | --edit-command)
edit_command="\${2}"
edit="true"
shift 2;;
-k | --keep-file)
keep_file="\${2}"
shift 2;;
*)
upload_files=("\${@}")
break;;
esac
done

if [ -z "\${upload_files}" ]; then
  upload_files[0]=""
fi

for upload_file in "\${upload_files[@]}"; do

  if [ -z "\${upload_file}" ]; then
    cd "\${file_dir}" || exit 1

    # new filename with date
    img_file="\$(date +"\${file_name_format}")"
    take_screenshot "\${img_file}"
  else
    # upload file instead of screenshot
    img_file="\${upload_file}"
  fi

  # get full path
  img_file="\$(cd "\$( dirname "\${img_file}")" && echo "\$(pwd)/\$(basename "\${img_file}")")"

  # check if file exists
  if [ ! -f "\${img_file}" ]; then
    echo "file '\${img_file}' doesn't exist !"
    exit 1
  fi

  # open image in editor if configured
  if [ "\${edit}" = "true" ]; then
    edit_cmd=\${edit_command//\%img/\${img_file}}
    echo "Opening editor '\${edit_cmd}'"
    if ! (eval "\${edit_cmd}"); then
      echo "Error for image '\${img_file}': command '\${edit_cmd}' failed, not uploading. For more information visit https://github.com/jomo/imgur-screenshot/wiki/Troubleshooting" | tee -a "\${log_file}"
      notify error "Something went wrong :(" "Information has been logged"
      exit 1
    fi
  fi

  upload_file "\${img_file}"

  # delete file if configured
  if [ "\${keep_file}" = "false" ] && [ -z "\${1}" ]; then
    echo "Deleting temp file \${img_file}"
    rm -rf "\${img_file}"
  fi

  echo ""
done`;

uploaders.sharexConfig = token =>
  JSON.stringify(
    {
      DestinationType: "ImageUploader",
      RequestURL: `${window.client.endpoint}/upload`,
      FileFormName: "f",
      Headers: {
        Authorization: token
      },
      URL: "$json:url$"
    },
    null,
    2
  );

uploaders.kshareConfig = token =>
  JSON.stringify(
    {
      name: "elixire",
      desc: "elixire is the future",
      target: `${window.client.endpoint}/upload`,
      format: "multipart-form-data",
      base64: false,
      headers: {
        Authorization: token
      },
      body: [
        {
          "__Content-Type": "/%contenttype/",
          name: "f",
          filename: "/image.%format/",
          body: "/%imagedata/"
        }
      ],
      return: ".url"
    },
    null,
    2
  );

export default uploaders;
