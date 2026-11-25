use framework "Foundation"
use scripting additions

property dayFormatter : missing value
property timestampFormatter : missing value

on run argv
    if (count of argv) is not 3 then error "Expected list name, parent ID, and creation day."
    set scopeList to item 1 of argv
    set scopeParent to item 2 of argv
    set scopeDay to item 3 of argv
    set dayFormatter to my makeFormatter("yyyy-MM-dd")
    set timestampFormatter to my makeFormatter("yyyy-MM-dd'T'HH:mm:ssXXX")

    set cutoffDate to missing value
    if scopeDay is not "" then
        -- Set components instead of parsing a locale-dependent date string.
        set cutoffDate to current date
        set day of cutoffDate to 1
        set year of cutoffDate to (text 1 thru 4 of scopeDay) as integer
        set month of cutoffDate to (text 6 thru 7 of scopeDay) as integer
        set day of cutoffDate to (text 9 thru 10 of scopeDay) as integer
        set time of cutoffDate to 0
    end if

    tell application "Things3"
        set sourceContainer to missing value
        if scopeList is not "" then
            set sourceContainer to list scopeList
        else if scopeParent is not "" then
            if exists project id scopeParent then
                set sourceContainer to project id scopeParent
            else if exists area id scopeParent then
                set sourceContainer to area id scopeParent
            end if
        else
            set sourceContainer to application "Things3"
        end if

        if sourceContainer is missing value then
            set candidates to {}
        else if cutoffDate is missing value then
            set candidates to get to dos of sourceContainer
        else
            set candidates to get (to dos of sourceContainer whose creation date is greater than or equal to cutoffDate)
        end if
    end tell

    set exportedItems to current application's NSMutableArray's array()
    repeat with todoRef in candidates
        exportedItems's addObject:(my recordForTodo(contents of todoRef))
    end repeat
    set responseObject to current application's NSMutableDictionary's dictionary()
    responseObject's setObject_forKey_(exportedItems, "items")
    responseObject's setObject_forKey_(exportedItems's |count|(), "candidate_count")
    set jsonData to current application's NSJSONSerialization's dataWithJSONObject_options_error_(responseObject, 0, missing value)
    if jsonData is missing value then error "Could not serialize Things records."
    return (current application's NSString's alloc()'s initWithData_encoding_(jsonData, current application's NSUTF8StringEncoding)) as text
end run

on recordForTodo(todoRef)
    set projectName to my nullValue()
    set areaName to my nullValue()
    set parentID to my nullValue()
    tell application "Things3"
        set taskID to id of todoRef
        set taskTitle to my textValue(name of todoRef)
        set taskNotes to my textValue(notes of todoRef)
        set tagNames to get name of every tag of todoRef
        set nativeStatus to status of todoRef
        if nativeStatus is completed then
            set statusName to "completed"
        else if nativeStatus is canceled then
            set statusName to "canceled"
        else if nativeStatus is open then
            set statusName to "open"
        else
            error "Unknown Things status."
        end if
        set activationDay to activation date of todoRef
        set deadlineDay to due date of todoRef
        set createdAt to creation date of todoRef
        set modifiedAt to modification date of todoRef
        set completedAt to completion date of todoRef
        set canceledAt to cancellation date of todoRef

        set taskProject to project of todoRef
        if taskProject is not missing value then
            set projectName to my textValue(name of taskProject)
            set parentID to id of taskProject
            set taskArea to area of taskProject
        else
            set taskArea to area of todoRef
        end if
        if taskArea is not missing value then
            set areaName to my textValue(name of taskArea)
            if taskProject is missing value then set parentID to id of taskArea
        end if
    end tell

    set outputItem to current application's NSMutableDictionary's dictionary()
    set tagArray to current application's NSArray's arrayWithArray:tagNames
    outputItem's setObject_forKey_(taskID, "id")
    outputItem's setObject_forKey_(taskTitle, "title")
    outputItem's setObject_forKey_(taskNotes, "notes")
    outputItem's setObject_forKey_(tagArray, "tags")
    outputItem's setObject_forKey_(statusName, "status")
    outputItem's setObject_forKey_(my dateValue(activationDay, true), "activation_date")
    outputItem's setObject_forKey_(my dateValue(deadlineDay, true), "deadline_date")
    outputItem's setObject_forKey_(my dateValue(createdAt, false), "creation_date")
    outputItem's setObject_forKey_(my dateValue(modifiedAt, false), "modification_date")
    outputItem's setObject_forKey_(my dateValue(completedAt, false), "completion_date")
    outputItem's setObject_forKey_(my dateValue(canceledAt, false), "cancellation_date")
    outputItem's setObject_forKey_(projectName, "project")
    outputItem's setObject_forKey_(areaName, "area")
    outputItem's setObject_forKey_(parentID, "list_id")
    return outputItem
end recordForTodo

on makeFormatter(formatString)
    set formatter to current application's NSDateFormatter's alloc()'s init()
    formatter's setLocale:(current application's NSLocale's localeWithLocaleIdentifier:"en_US_POSIX")
    formatter's setTimeZone:(current application's NSTimeZone's localTimeZone())
    formatter's setDateFormat:formatString
    return formatter
end makeFormatter

on dateValue(nativeDate, calendarDay)
    if nativeDate is missing value then return my nullValue()
    if calendarDay then
        return (dayFormatter's stringFromDate:nativeDate) as text
    end if
    return (timestampFormatter's stringFromDate:nativeDate) as text
end dateValue

on nullValue()
    return current application's NSNull's |null|()
end nullValue

on textValue(nativeText)
    if nativeText is missing value then return ""
    return nativeText as text
end textValue
