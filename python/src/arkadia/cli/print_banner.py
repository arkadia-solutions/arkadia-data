import sys
import textwrap
from .colors import C

# --- LOGO (Raw f-string fix) ---
def get_logo(color_accent=C.AID_ACCENT):
    return fr"""{color_accent}                                                               
                                   ; i  :J                                      
                               U, .j..fraaM.  nl                                
                            b h.obWMkkWWMMWMCdkvz,k                             
                         ! .mQWM:o hiMoMW v.uaXMdohbi                           
                        hI,MMmaIao.Wo .IMkoh FCMwqoXa                           
                      ,.c.aWdM. d,aToW  .    Mb!. MopfQ.L                       
                       jhj.xoM :k    aCu F: w MpmqMvMMI,I                       
                      bzMhz:W    .Mw . o lYh ai M iMa pM.j                      
                     hzqWWM;    M;o.WMWWMkMX f.a aa bModpo.                     
                     ;tMbbv   xp oJMMWWWWMMMM iv  dLMXakM:T                     
                       mdh        MMWWWWWWWbQLCzurjktvMor                       
                      ,QFw ;M,b .MWWWWWWWMWMWd  xz   M,kd X                     
                      qjMIo IMTW.WWWWWMWWWM.o.I   rpULaMdi.                     
                       .mMM  uoWWWMWWWWWWp qM,,M l M;mMbrI                      
                        f nm  MMW MWWjMuMj  I  o   LbMac                        
                              WWdMWWWW Mv a.b..aauMhMwQf                        
                              MoWWW,WWtjonJMWtoMdoaoMI                          
                              MMMM Mi    xd:Mm tMwo Cr,                         
                             xMMc .otqokWMMMao:oio.                             
                             MW    .   C..MkTIo                                 
                            WW                                                  
                           QWM                                                  
                           WW                                                   
                          uMW                                                   
                          WW                                                    
                          MW{C.RESET}"""

def print_banner(
    tool_name: str, 
    version: str, 
    color: str = C.AID_MAIN,
    description: str = "", 
    metadata: dict = None
):
    """
    Prints a standardized, responsive banner for Arkadia Tools.
    """
    # 1. Print Logo
    print(get_logo(color_accent=color))
    
    # 2. Print Header (Tool Name)
    # Arkadia prefix in Green, Tool name in White Bold
    print(f"\n\n   {C.AID_MAIN}Arkadia{C.RESET} {C.BOLD}{C.WHITE}{tool_name.upper()}{C.RESET}")
    print(f"   {C.DIM}{'-' * 50}{C.RESET}")

    # 3. Print Description (Wrapped)
    if description:
        # Wrap text to 60 chars for neatness, indented by 3 spaces
        wrapped = textwrap.fill(description, width=65)
        indented_desc = textwrap.indent(wrapped, "   ")
        print(f"{C.WHITE}{indented_desc}{C.RESET}\n")

    # 4. Print Metadata (Version, Model, Stats, etc.)
    # Format:  Label:    Value
    print(f"   {C.DIM}Version:{C.RESET} \t{C.YELLOW}{version}{C.RESET}")
    
    if metadata:
        for key, value in metadata.items():
            # Align keys if needed, but simple tab is usually fine
            print(f"   {C.DIM}{key}:{C.RESET} \t{C.CYAN}{value}{C.RESET}")

    print("\n") # Extra spacing at bottom