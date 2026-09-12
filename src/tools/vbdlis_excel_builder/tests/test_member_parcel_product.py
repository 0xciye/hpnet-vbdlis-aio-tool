from tools.vbdlis_excel_builder.core.household_parser import HouseholdParser
from tools.vbdlis_excel_builder.models import MappingProfile


def test_repeated_member_rows_do_not_multiply_people_or_drop_parcels():
    rows=[]
    people=[("NGUYỄN VĂN A","030064013684"),("NGUYỄN THỊ B","030200012345"),("NGUYỄN VĂN C","030202067890")]
    row_number=1
    for parcel in (100,101):
        for index,(name,cccd) in enumerate(people):
            row_number+=1
            rows.append({"_row":row_number,"A":1 if row_number==2 else None,"B":name,"C":cccd,"D":10,"E":parcel,"F":100})
    profile=MappingProfile(source_mapping={
        "household_stt":"A","person_name":"B","cccd":"C","sheet_number":"D","parcel_number":"E","area":"F"
    })

    households,issues,stats=HouseholdParser().parse(rows,profile)

    assert stats["households"]==1 and stats["people"]==3 and stats["parcels"]==2
    assert len(households[0].people)*len(households[0].parcels)==6
    assert sum(issue.code=="DUPLICATE_PERSON_ROW_MERGED" for issue in issues)==3


def test_letter_parcel_is_explicitly_rejected():
    rows=[{"_row":2,"A":1,"B":"NGUYỄN VĂN A","C":"031080001234","D":92,"E":"CN","F":100}]
    profile=MappingProfile(source_mapping={
        "household_stt":"A","person_name":"B","cccd":"C","sheet_number":"D","parcel_number":"E","area":"F"
    })

    households,issues,stats=HouseholdParser().parse(rows,profile)

    assert stats["parcels"]==0 and households[0].parcels==[]
    assert any(issue.code=="INVALID_PARCEL_IDENTIFIER" for issue in issues)
