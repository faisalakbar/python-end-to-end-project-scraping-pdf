*** Settings ***
Library    ${CURDIR}${/}epaper_downloader.py
Library    ${CURDIR}${/}baugesuch_reader.py
Library    OperatingSystem

*** Variables ***
${INPUT_DIR}       ${CURDIR}${/}input
${PDF_PATH}        ${INPUT_DIR}${/}limmatwelle-22-mai.pdf
${OUTPUT_JSON}     ${CURDIR}${/}output${/}wurenlos_baugesuch.json
${PAGE_NUM}        12

*** Tasks ***
Download And Parse Wurenlos Baugesuch
    Create Directory    ${INPUT_DIR}
    ${saved}=    Download Issue Pdf    ${PDF_PATH}
    File Should Exist    ${saved}
    ${json}=    Parse Baugesuch From Pdf    ${saved}    ${PAGE_NUM}    ${OUTPUT_JSON}    scan_all=${False}
    Log To Console    ${json}