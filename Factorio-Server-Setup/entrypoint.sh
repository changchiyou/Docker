#!/bin/bash

MAPSHOT_ROOT_DIRECTORY=${MAPSHOT_ROOT_DIRECTORY:-"/mapshot"}
MAPSHOT_FACTORIO_DATA_DIRECTORY=${MAPSHOT_FACTORIO_DATA_DIRECTORY:-"${MAPSHOT_ROOT_DIRECTORY}/factorio"}
MAPSHOT_FACTORIO_BINARY_PATH=${MAPSHOT_FACTORIO_BINARY_PATH:-"$MAPSHOT_ROOT_DIRECTORY/factorio/bin/x64/factorio"}
MAPSHOT_WORKING_DIRECTORY=${MAPSHOT_WORKING_DIRECTORY:-"$MAPSHOT_ROOT_DIRECTORY/factorio"}
MD5_RECORD_FILE="$MAPSHOT_ROOT_DIRECTORY/factorio_save.md5"

# Check if Factorio exists
echo "Checking if Factorio exists"
if [ ! -f "$MAPSHOT_FACTORIO_BINARY_PATH" ]; then
    echo "Factorio does not exist, downloading..."
    if [[ -z $FACTORIO_USERNAME || -z $FACTORIO_TOKEN ]]; then
        echo "Could not authenticate. Please confirm that the environment variables FACTORIO_USERNAME & FACTORIO_TOKEN are set correctly"
        echo "  FACTORIO_USERNAME: '$FACTORIO_USERNAME'"
        echo "  FACTORIO_TOKEN: '$FACTORIO_TOKEN'"
        echo "Exiting..."
        exit 1
    fi
    curl "https://www.factorio.com/get-download/${RELEASE_VERSION:-"stable"}/${RELEASE_TYPE:-"alpha"}/linux64?username=$FACTORIO_USERNAME&token=$FACTORIO_TOKEN" -L -o /root/factorio-linux64.tar.xz
    echo "Extracting..."
    tar xvf /root/factorio-linux64.tar.xz -C "$MAPSHOT_ROOT_DIRECTORY"
    mkdir -p "$MAPSHOT_FACTORIO_DATA_DIRECTORY/mods"
    echo '{}' > "$MAPSHOT_FACTORIO_DATA_DIRECTORY/mods/mod-list.json"
else
    echo "Factorio exists, proceeding without download"
fi

MAPSHOT_SAVE_NAME=$(basename "$FACTORIO_SAVE" .zip)
MAPSHOT_SCRIPT_OUTPUT_DIR="$MAPSHOT_ROOT_DIRECTORY/factorio/script-output/mapshot/$MAPSHOT_SAVE_NAME"

# Determine mode
if [ "$MAPSHOT_MODE" == "render" ]; then
    echo 'Mapshot mode set to "render", proceeding with render.'
    calculate_md5() {
        md5sum "$FACTORIO_SAVE" | awk '{ print $1 }'
    }

    current_md5=$(calculate_md5)
    previous_md5=$(cat "$MD5_RECORD_FILE" 2>/dev/null || echo "")

    if [ "$current_md5" != "$previous_md5" ]; then
        echo "Save file has changed or no previous record. Proceeding with render."
        echo "$current_md5" > "$MD5_RECORD_FILE"

        # Delete old d-* folders except the latest one
        if [ -d "$MAPSHOT_SCRIPT_OUTPUT_DIR" ]; then
            echo "Cleaning up old d-* directories..."
            cd "$MAPSHOT_SCRIPT_OUTPUT_DIR"
            ls -dt d-* | tail -n +2 | xargs rm -rf
            echo "Cleanup complete."
        else
            echo "No previous mapshot directories to clean."
        fi

        echo 'Rendering map...'
        timeout "$MAPSHOT_INTERVAL" xvfb-run -a mapshot render --logtostderr --factorio_binary "$MAPSHOT_FACTORIO_BINARY_PATH" --factorio_datadir "$MAPSHOT_FACTORIO_DATA_DIRECTORY" --work_dir "$MAPSHOT_WORKING_DIRECTORY" --area "${MAPSHOT_AREA:-all}" --tilemin "${MAPSHOT_MINIMUM_TILES:-64}" --tilemax "${MAPSHOT_MAXIMUM_TILES:-0}" --jpgquality "${MAPSHOT_JPEG_QUALITY:-90}" --minjpgquality "${MAPSHOT_MINIMUM_JPEG_QUALITY:-90}" --surface "${MAPSHOT_SURFACES_TO_RENDER:-"_all_"}" "${MAPSHOT_VERBOSE_FACTORIO_LOGGING:-"--factorio_verbose"}" -v "${MAPSHOT_VERBOSE_MAPSHOT_LOG_LEVEL_INT:-9}" "$FACTORIO_SAVE"
    else
        echo "No changes in the save file. Skipping render."
    fi
elif [ "$MAPSHOT_MODE" == "serve" ]; then
    echo 'Mapshot mode set to "serve", serving map...'
    mapshot serve --factorio_binary "$MAPSHOT_FACTORIO_BINARY_PATH" --factorio_datadir "$MAPSHOT_FACTORIO_DATA_DIRECTORY" --work_dir "$MAPSHOT_WORKING_DIRECTORY"
else
    echo 'Invalid $MAPSHOT_MODE. Please set it to "render" or "serve". Exiting...'
    exit 1
fi
