from types import SimpleNamespace as P
from swipe import PageGesture


def hand(x=.5, y=.55, opened=True):
    # A simplified palm; tips extend away from the wrist only when open.
    points = [P(x=x,y=y+.15) for _ in range(21)]
    for mcp,pip,tip,dx in ((5,6,8,-.09),(9,10,12,-.03),(13,14,16,.03),(17,18,20,.09)):
        points[mcp] = P(x=x+dx,y=y-.04)
        points[pip] = P(x=x+dx,y=y-.15)
        points[tip] = P(x=x+dx,y=y-.30 if opened else y+.08)
    return points


def arm(g, now=0):
    g.update(hand(),now)
    result=g.update(hand(),now+.4)
    assert result.progress == 1


def test_left_swipe_next_and_return_does_not_reverse():
    g=PageGesture()
    arm(g)
    result=g.update(hand(.25),.6)
    assert result.page==1
    assert g.update(hand(.5),.8).page==0
    assert g.update(hand(.8),1.2).page==0
    assert g.update(hand(.5),1.6).page==0
    assert g.update(hand(.5),2.0).progress==1
    assert g.update(hand(.75),2.2).page==-1


def test_closed_hand_and_unarmed_motion_do_not_turn_pages():
    g=PageGesture()
    assert g.update(hand(.2),0).page==0
    assert g.update(hand(.8),.3).page==0
    g.update(hand(opened=False),.5)
    result=g.update(hand(.2,opened=False),1)
    assert result.page==0
    assert g.anchor is None


def test_lost_hand_requires_rearming():
    g=PageGesture()
    arm(g)
    g.update(None,.5)
    assert g.update(hand(.2),.6).page==0


def test_slow_or_vertical_motion_is_rejected():
    g=PageGesture()
    arm(g)
    g.update(hand(.43),.6)
    assert g.update(hand(.25),1.6).page==0
    arm(g,2)
    assert g.update(hand(.25,.9),2.6).page==0


def test_hover_does_not_turn_pages():
    g=PageGesture()
    arm(g)
    for t in range(1,20):
        assert g.update(hand(.50+(t%2)*.015),float(t)).page==0
